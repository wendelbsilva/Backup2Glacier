
import boto3
import hashlib
from binascii import hexlify
import os
import datetime
from math import floor, ceil
import compress

from inventory import Inventory, File

class Glacier:

    def __init__(self, _vaultName):
        self.glacier = boto3.client("glacier")
        self.res = boto3.resource("glacier")
        
        self.vaultName = _vaultName
        self.vault = self.res.Vault("-", self.vaultName)
        
        self.inventory = None
        self.files = None
        self.active_jobs = []
        

    def uploadFileMultiPart(self, filename):
        #   The part size must be a megabyte (1024 KB) multiplied by a power of 2,
        # for example 1048576 (1 MB), 2097152 (2 MB), 4194304 (4 MB), 8388608 (8 MB),
        # and so on. The minimum allowable part size is 1 MB, and the maximum
        # is 4 GB (4096 MB).
        # size: Size of each part in bytes, except the last. The last part can be smaller.
        size = 1024*1024*pow(2,7) #2^7 = 128 --> 128mb per part
        multipartDict = self.glacier.initiate_multipart_upload(vaultName=self.vaultName,
                                                               archiveDescription=filename, partSize=str(size))
        res = boto3.resource("glacier")
        print("Requesting Multipart Job")
        multipart = res.MultipartUpload("-",self.vaultName, multipartDict["uploadId"])
        print("Job Id Received, Initializing Multipart Upload")

        # Read File
        total = os.path.getsize(filename)
        f = open(filename,"rb")
        data = f.read(size)
        last = 0
        while (data):
            sha256 = self.sha256treePartial(data)
            if (len(data) != size): size = len(data)
            partRange = "bytes {0}-{1}/*".format(last, (last+size-1)) # Format '0-4194303'
            #print("Sending Part:",partRange, sha256)
            ret = multipart.upload_part(vaultName=self.vaultName,range=partRange, body=data)#, checksum=sha256)
            #print("Return:",ret)
            last += len(data)
            print("Progress:", floor(100*last/total), "%") 
            #
            data = f.read(size)
            #TODO: compare checksum
        print("All Files Uploaded")
        sha256 = self.sha256tree(f)
        archive = multipart.complete(archiveSize=str(last), checksum=sha256)
        print("Upload Completed:",archive)

    def uploadDirectory(self, f):
        name = os.path.basename(f).replace(".","_")
        n = datetime.datetime.now()
        name = name + n.strftime("-%Y_%m_%d")
        name = name + ".tar.gz"
        print("Compressing Directory into a Temporary File")
        compress.compressDir(name, f)
        self.uploadFileMultiPart(name)
        os.remove(name)
        print("Removed Temporary Compressed Directory")
        print("Directory Uploaded Successfully")

    def uploadFile(self, filename):
        # Read File
        f = open(filename,"rb")
        data = f.read()
        comcheck = self.sha256tree(f)
        # Upload File
        t = self.glacier.upload_archive(vaultName=self.vaultName,archiveDescription=filename,body=data)
        status = t["ResponseMetadata"]["HTTPStatusCode"]
        aid = t["archiveId"]
        checksum = t["checksum"]
        
        txtStatus = "File Uploaded Successfully!"
        if (status != 201): txtStatus = "Something went wrong: " + str(status)

        # TODO: Update Inventory
        newFile = File( {"Size":os.path.getsize(filename),
                         "CreationDate": datetime.datetime.utcnow().isoformat(),
                         "ArchiveDescription": filename,
                         "ArchiveId": aid,
                         "SHA256TreeHash": checksum} )
        newFile.isNew = True
        self.inventory.files.append( newFile )
        #TODO: Do checksum comparison
        return aid, txtStatus, checksum, comcheck

    def deleteFile(self, ffile):
        print("Deleting....", ffile.aid)
        self.glacier.delete_archive(vaultName=self.vaultName, archiveId=ffile.aid)
        ffile.deleted = True

    def initListFiles(self):
        #res = boto3.resource("glacier")
        #vault = res.Vault("-", self.vaultName)
        a = self.vault.initiate_inventory_retrieval()
        #TODO: give some kind of feedback
        self.active_jobs.append(a.job_id)

    def listJobs(self):
        j = self.glacier.list_jobs(vaultName=self.vaultName)
        print(j)
        ret = []
        for job in j["JobList"]:
            if (job["StatusCode"] == "Succeeded" and job["Action"] == "InventoryRetrieval"):
                if (self.inventory == None or
                    self.inventory.date < dateutil.parser.parse(job["CreationDate"])):
                    a = self.res.Job("-",self.vaultName, job["JobId"])
                    data = a.get_output()["body"]
                    #TODO: Only update inventory if needed. Dont want to lose new/deleted info
                    self.inventory = Inventory( json.loads(data.read().decode("utf-8")) )
        return j["JobList"]

    def loadDefault(self):
        if (os.path.isfile("inventory.pkl")):
            fInv = open("inventory.pkl", "rb")
            self.inventory = pickle.load(fInv)
        else:
            self.listJobs()

    def closeDefault(self):
        if (self.inventory != None):
            fInv = open("inventory.pkl","wb")
            pickle.dump( self.inventory, fInv )
            fInv.close()

    def sha256tree(self, f):
        f.seek(0, 0)
        thash = []
        size = 1024*1024 # 1MV
        data = f.read( size )
        while (data != b""):
            thash.append( hashlib.sha256(data).digest() )
            data = f.read( size )       
        while (len(thash) > 1):
            temp = thash
            thash = []
            while (len(temp) > 1):
                data = temp[0] + temp[1]
                temp = temp[2:]
                thash.append( hashlib.sha256(data).digest() )
            if (len(temp) == 1): thash.append( temp[0] )
        return hexlify( thash[0] ).decode("ascii")

    def sha256treePartial(self, full_data):
        thash = []
        size = 1024*1024 # 1MV
        last = 0
        data = full_data[last: last+size]
        while (data != b""):
            thash.append( hashlib.sha256(data).digest() )
            last += size
            data = full_data[last: last+size]
        while (len(thash) > 1):
            temp = thash
            thash = []
            while (len(temp) > 1):
                data = temp[0] + temp[1]
                temp = temp[2:]
                thash.append( hashlib.sha256(data).digest() )
            if (len(temp) == 1): thash.append( temp[0] )
        return hexlify( thash[0] ).decode("ascii")
