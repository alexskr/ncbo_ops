#/usr/bin/env python
#
# CS 50 Final Project
#
# Simple script to deal with flaky/overloaded 4store (RDF tripple store/graph database) used in NCBO BioPortal stack
# Script scrapes a status page of 4store (usually on fqdn:8080/status)
# it sends a notitication to OPS slack channel if 4store outstating query backlog is higher than warning limit 
# it restarts 4store when two conditions are met:
#  1. outstading query backlog is over the critical limit 
#  2. ncbo_cron is not running any jobs
# 
# Usage:
# Need to set BOT_ID and SLACK_BOT_TOKEN environment variable before running script
# Script is usually run with cron
#
# Used resources: 
# https://www.fullstackpython.com/blog/build-first-slack-bot-python.html
# 
# Author: Alex Skrenchuk
# version: 1
# 7/28/2016

import requests
import bs4 #beautiful soup - used for parsing HTML
import os, sys, getopt
import redis

#slack related initialization
from slackclient import SlackClient
BOT_ID = os.environ.get("BOT_ID")
slack_client = SlackClient(os.environ.get('SLACK_BOT_TOKEN'))

#Set Defaults
redishost = 'localhost'
redisport = '6379'
fsSrv = 'localhost'
serviceName = '4s-httpd-ontologies_api'
verbose = False
#thresholds
warning = 50
critical = 100

def printUsage():
  "Print usage instructions"
  print ("usage: check4store -vmf -r redis host -p redis port -f 4store host")
  print ("-r: redis host\n-p: redis port number\n-v: verbose\n-f: 4store host name")
  print ("example: check4store.py -h 4store.domain -r redishost.domain -p 6380 -v")
  return

def statusCheck():
  "scrapes status page and returns metrics"

  #4store server info page
  statusPageUrl='http://' + fsSrv + ':8080/status/'

  #read status page
  page = requests.get(statusPageUrl, timeout=30)

  #we need to handle exeptions including 404, 500 errors.
  try:
    page.raise_for_status()
  except Exception as exc:
    print('there was a problem: ', exc)

  #extract metrics from the status page
  # parse status page
  statusPage = bs4.BeautifulSoup(page.text, "html.parser")
  # extract elements in the table
  elements = statusPage.select('td')
  # read the header of the page; we will need it to verify we are looking at the correct page.
  title = statusPage.h1.string.split()
  metrics = [0,0]
  if title[0] == 'SPARQL' and len(elements) == 2:
    # looks like we are getting correct status page
    runq = (int(elements[0].string))
    # oustanding queries is the 2nd element in the table
    outq = (int(elements[1].string))
    if verbose:
      print("status page for "+fsSrv+" :")
      print("Run queue is :"+ str(runq))
      print("Outstanding queue is :"+ str(outq))
  else:
    # we are not getting the page we expect
    slackpost ("Something is wacky with the 4store status script")
    quit()
  metrics = [ runq, outq]
  return metrics
  
  def serviceRestart():
  "restart 4store service"
  if verbose:
    print("restarting 4store")
  if fsSrv == 'localhost':
    subprocess.call(["/sbin/service " + serviceName + " restart"])
  else:
    subprocess.call(["remctl " + fsSrv + " restart4store"])

def isParsing() :
  "checks redis for any ncbo_cron parsing activity"
  #this function is not yet functional, so always return false
  return False
  r = redis.StrictRedis(host=redishost, port=redisport)
  try:
    process_status = r.get("process_status")
  except redis.ConnectionError:
    sys.exit("can't connect to redis running on %s" % redishost)

  if process_status == 'processing':
     return True
  else:
     return False
     
# Read command line args
myopts, args = getopt.getopt(sys.argv[1:],"r:p:vfs:h:")

for o, a in myopts:
  if o == '-r':
    redishost = a
  if o == '-p':
    redisport = a
  if o == '-v':
    verbose = True
  if o == '-h':
    fsSrv = a
  if o == '-s':
    service = a

#print usage instructions and exit if if no arguments are passed
if len(myopts) == 0:
  mprintUsage()
  sys.exit()

metrics = statusCheck()
outq = metrics[1]

#Main Logic here:
if outq > critical:
   if isParsing():
     # can't restart 4store so we should notify OPS, they should make the call to restart 4store
     slackpost(":finnadie: 4store is practially dead! it has " + str(outq) + " outstanding queries and ncbo_cron is runing.  Someone needs to t
ake a look or else...")
   else:
     slackpost (":godmode: 4store is choking preety bad, it has " + str(outq) + " outstanding queries. \n RESTARTING 4store")
     #serviceRestart()
elif outq > warning:
  slackpost(":hurtrealbad: 4store is choking! it has " + str(outq) + " outstanding queries! Someone should take a look at it")
else:
  if verbose:
    print("status is normal")
