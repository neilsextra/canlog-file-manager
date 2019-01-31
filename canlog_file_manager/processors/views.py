from flask import Flask, Blueprint, render_template, request
import binascii
import ctypes
import codecs
import struct
import sys
import re
import argparse
import csv
import io
import re
import json
import threading
import datetime
from os import environ
import os
import tempfile
import uuid
import azure.storage.blob
import string
import multiprocessing as mp
import gc

from struct import unpack, pack
from azure.storage.common import CloudStorageAccount
from azure.storage.blob.models import BlobBlock

views = Blueprint('views', __name__, template_folder='templates')

class CanlogParser:
   def __init__(__self, file):
      __self.__file = file 
      __self.__fileIdentifier = None
      __self.__formatIdentifier = None
      __self.__programIdentifier = None
      __self.__byteOrder = None

      __self.__floatingPointFormat = None
      __self.__versionNumber = None
      __self.__versionNumberConv = None
      __self.__codePageNumber = None

      __self.__recordingDate = None
      __self.__recordingTime = None    
      __self.__authorsName = None    
      __self.__orgName = None    
      __self.__projectName = None    
      __self.__subjectName = None   
      __self.__timeStamp = None    
      __self.__timeOffset = None    
      __self.__timeQualityPass = None    
      __self.__timeIdentification = None  
   
   def log(__self, message):
      __self.__file.write(str(datetime.datetime.now()))
      __self.__file.write(' : ')
      __self.__file.write(message)
      __self.__file.write('\n')
      __self.__file.flush()

   def parse(__self, filePath):
      file = open(filePath, "rb")
      
      with file:
            __self.__fileIdentifier = file.read(8)
            __self.__formatIdentifier = file.read(8)
            __self.__programIdentifier = file.read(8)
            __self.__byteOrder = file.read(2)
            __self.__floatingPointFormat = file.read(2)
            __self.__versionNumber = file.read(2)
            __self.__codePageNumber = file.read(2)
            
            __self.__reserved01 = file.read(2)
            __self.__reserved02 = file.read(26)
            __self.__uptoDateCGBlock = file.read(2)
            __self.__uptoDateSRBlock = file.read(2)

            __self.__headerLink = file.tell()

            __self.__headerHD = file.read(2)
            __self.__blockSizeHD = file.read(2)    

            __self.__linkDGB = file.read(4)    
            __self.__linkFC = file.read(4)    
            __self.__linkPRB = file.read(4)    
         
            __self.__groupNumber = file.read(2)    

            __self.__recordingDate = file.read(10)    
            __self.__recordingTime = file.read(8)    
            __self.__authorsName = file.read(32)    
            __self.__orgName = file.read(32)    
            __self.__projectName = file.read(32)    
            __self.__subjectName = file.read(32)    
            julianTime = datetime.datetime.strptime(__self.__recordingDate.decode('ascii') + ' ' +
                                                    __self.__recordingTime.decode('ascii'), "%d:%m:%Y %H:%M:%S").timestamp()
            __self.__timestamp = re.sub('\..*$', '', str(julianTime))
                 
   def getSummary(__self):
      print("HD Block: " + (__self.__headerHD.decode('ascii')))
      print("file_identifier: " + (__self.__fileIdentifier.decode('ascii')))
      print("formatIdentifier: " + (__self.__formatIdentifier.decode('ascii')))
      print("versionNumber: " + str(struct.unpack("H",  __self.__versionNumber)[0]))
      print("recordingDate: " +__self.__recordingDate.decode('ascii'))
      print("recordingTime: " +__self.__recordingTime.decode('ascii'))
      print("recordingTime: " +__self.__recordingTime.decode('ascii'))
      print("julianTime: " + __self.__timestamp)
       
      summary = {
         "file_identifier": __self.__fileIdentifier.decode('ascii') ,
         "format_identifier": __self.__formatIdentifier.decode('ascii'), 
         "versionNumber": str(struct.unpack("H",  __self.__versionNumber)[0]),
         "recordingDate": __self.__recordingDate.decode('ascii'),
         "recordingTime": __self.__recordingTime.decode('ascii'),
         "timestamp": __self.__timestamp
      } 

      return summary

def getConfiguration():    
   account_key = None
   account_name = None
   default_folder_name = None
   container_name = None
   save_files = 'true'
   socket_timeout = None
   staging_dir = None
   debug_file = None

   try:
      import canlog_file_manager.configuration as config

      account_name = config.ACCOUNT_NAME
      container_name = config.CONTAINER_NAME
      default_folder_name = config.DEFAULT_FOLDER_NAME
      save_files = config.SAVE_FILES
      socket_timeout = config.SOCKET_TIMEOUT
      debug_file = config.DEBUG_FILE
      staging_dir = config.STAGING_DIR
   
   except ImportError:
      pass

   try:
      import canlog_file_manager.keys as keys
      account_key = keys.ACCOUNT_KEY

   except ImportError:
      pass

   account_key = environ.get('ACCOUNT_KEY', account_key)
   account_name = environ.get('ACCOUNT_NAME', account_name)
   container_name = environ.get('CONTAINER_NAME', container_name)
   default_folder_name = environ.get('DEFAULT_FOLDER_NAME', default_folder_name)
   save_files = environ.get('SAVE_FILES', save_files)
   socket_timeout = environ.get('SOCKET_TIMEOUT', socket_timeout)
   debug_file = environ.get('DEBUG_FILE', debug_file)
   staging_dir = environ.get('STAGING_DIR', staging_dir)

   return {
      "account_key": account_key,
      "account_name": account_name,
      'container_name': container_name,
      'default_folder_name': default_folder_name,
      'save_files': save_files,
      'socket_timeout': socket_timeout,
      'debug_file': debug_file,
      'staging_dir': staging_dir
      
   }   

def store(f, file_name, summary):
   configuration = getConfiguration()

   log(f, 'Account Name: ' + configuration['account_name'])
   log(f, 'Container Name: ' + configuration['container_name'])
   
   account = CloudStorageAccount(account_name=configuration['account_name'], 
                                 account_key=configuration['account_key'])
   
   folder =  configuration['default_folder_name']

   service = account.create_block_blob_service()

   service.create_container(configuration['container_name']) 
   
   log(f, 'Storing Content')

   service.create_blob_from_stream(configuration['container_name'],  folder + '/' + summary['timestamp'] + '/summary.json',
                                   io.BytesIO(json.dumps(summary).encode()))

                                                  
   log(f, 'Stored: ' + file_name)       
   os.remove(file_name)

   log(f, 'Completed (Log) : ' + file_name + ' - ' + configuration['default_folder_name'] + ' - ' + summary['timestamp'])

   return


def process_canlog(f, file_name):
   print('Process_canlog: ' + file_name)
   parser = CanlogParser(f)
   parser.parse(file_name)
  
   return parser.getSummary()

def log(f, message):
   f.write(str(datetime.datetime.now()))
   f.write(' : ')
   f.write(message)
   f.write('\n')
   f.flush()

@views.route("/")
def home():
   return render_template("main.html")

@views.route("/list", methods=["GET"])
def list():
   configuration = getConfiguration()
   
   print()
   f = open(configuration['debug_file'], 'a')
   
   folder = request.args.get('folder')
   
   try:
      log(f, 'Listing Files - request received - [' + folder + ']')

      account = CloudStorageAccount(account_name=configuration['account_name'], 
                                    account_key=configuration['account_key'])
 
      service = account.create_block_blob_service()

      service.create_container(configuration['container_name']) 

      output = []

      blobs = service.list_blobs(configuration['container_name'])

      for blob in blobs:
         if (re.match("(.*)\/(.*)\/([s][u|t].*\.json)", blob.name,  re.DOTALL)):

            data = re.search("(.*)\/(.*)\/([s][u|t].*\.json)", blob.name, re.DOTALL)


            if (folder == '' or folder == data.group(1)):
               output.append({
                  "summary_file": blob.name,
                  "folder": data.group(1),
                  "timestamp": data.group(2),
                  "file_name": data.group(3)
               })
      
      f.close()

      return json.dumps(output, sort_keys=True)

   except Exception as e:
      log(f, str(e))

      f.close()
      return ""

@views.route("/retrieve", methods=["GET"])
def retrieve():
   timestamp = request.args.get('timestamp')

   configuration = getConfiguration()
   f = open(configuration['debug_file'], 'a')
   log(f, 'Retrieving - ' + timestamp)

   configuration = getConfiguration()

   account = CloudStorageAccount(account_name=configuration['account_name'], 
                                 account_key=configuration['account_key'])
 
   service = account.create_block_blob_service()

   stream = io.BytesIO()

   service.get_blob_to_stream(container_name=configuration['container_name'], 
                                   blob_name=configuration['default_folder_name'] + '/' + timestamp + '/can.json', stream=stream)

   log(f, 'Retrieved - ' + timestamp)

   return stream.getbuffer()

@views.route("/commit", methods=["GET"])
def commit():
   try:
      configuration = getConfiguration()

      guid = request.values.get('guid')
      folder = configuration['default_folder_name']
      
      print('GUID: ' + guid)

      blob_name = folder + '/' + guid + ".log"

      f = open(configuration['debug_file'], 'a')

      log(f, 'Committing: ' +  blob_name)
      
      account = CloudStorageAccount(account_name=configuration['account_name'], 
                                    account_key=configuration['account_key'])
   
      service = account.create_block_blob_service()

      blockslist = service.get_block_list(configuration['container_name'], blob_name, None, 'uncommitted')
      blocks = blockslist.uncommitted_blocks
      
      service.put_block_list(configuration['container_name'], blob_name, blocks)
      
      log(f, 'Committed: ' +  blob_name)
 
      output = {
         'status' : 'ok'
      }
 
   except Exception as e:
      log(f, str(e))
      f.close()
      output.append({
         "status" : 'fail',
         "error" : str(e)
      })
   
   return json.dumps(output, sort_keys=True)
   
@views.route("/process", methods=["GET"])
def process():
   output = []
   
   try:
      print('inside process [1]')
      configuration = getConfiguration()

      f = open(configuration['debug_file'], 'a')

      guid = request.values.get('guid')

      print('inside process [2]')

      folder = configuration['default_folder_name']
      print('inside process [3] ' + folder)

      blob_name = folder + '/' + guid + ".log"

      print('inside process [3] ' + blob_name)

      file_name = request.args.get('file_name')
      
      print('inside process [4] ' + file_name)
    
      summary = process_canlog(f, file_name)

      target_blob_name = folder + '/' + summary['timestamp'] + '/' + 'can.log'
      
      print('inside process [4] ' + target_blob_name)
     
      log(f, 'Renaming blob : ' + target_blob_name) 
      
      account = CloudStorageAccount(account_name=configuration['account_name'], 
                                    account_key=configuration['account_key'])
   
      service = account.create_block_blob_service()
      blob_url = service.make_blob_url(configuration['container_name'], blob_name)
      service.copy_blob(configuration['container_name'], target_blob_name, blob_url)
      
      log(f, 'Deleting temporary blob : ' + blob_name) 
 
      store(f, file_name, summary)

      return json.dumps(summary).encode()

   except Exception as e:
      log(f, str(e))
      f.close()
      output.append({
         "status" : 'fail',
         "error" : str(e)
      })
      
   return json.dumps(output, sort_keys=True)

@views.route("/upload", methods=["POST"])
def upload():
   configuration = getConfiguration()

   temp_file_name = request.values.get('file_name')

   guid = request.values.get('guid')
   folder = configuration['default_folder_name']
   chunk = request.values.get('chunk')

   blob_name = folder + '/' + guid + ".log"

   f = open(configuration['debug_file'], 'a')
   
   uploadedFiles = request.files
   
   fileContent = None

   for uploadFile in uploadedFiles:
      fileContent = request.files.get(uploadFile)
   
   output = []

   account = CloudStorageAccount(account_name=configuration['account_name'], 
                                 account_key=configuration['account_key'])
 
   service = account.create_block_blob_service()

   buffer = fileContent.read()

   if (temp_file_name == None or temp_file_name == ''):
      with tempfile.NamedTemporaryFile(delete=False) as tmpfile:
         temp_file_name = tmpfile.name

         log(f, 'Temp File Allocated allocated - ' + temp_file_name)

         with open(temp_file_name, 'ab') as temp:

            temp.write(buffer)
            temp.close()

         guid = str(uuid.uuid4())
         log(f, 'UUID allocated - ' + guid)

         blob_name = folder + '/' + guid + ".log"
         log(f, 'blob_name - ' + blob_name)

         service.create_container(configuration['container_name']) 
      
         log(f, "Created Container - [" +  (configuration['container_name']) + "] - " + blob_name)
            
   else:
      with open(temp_file_name, 'ab') as temp:

         temp.write(buffer)
         temp.close()
  
   print(temp_file_name + ' - ' + guid)
   service.put_block(configuration['container_name'], blob_name, buffer, chunk.zfill(32))

   output.append({
      "file_name" : temp_file_name,
      "guid" : guid,
      "folder" : folder,
      "chunk" : chunk
   })

   f.close()
   
   return  json.dumps(output, sort_keys=True)