#!/usr/bin/python3

import tkinter as tk
from tkinter import ttk
from tkinter import messagebox, filedialog
import boto3

import hashlib
import os
import dateutil.parser
import json
import datetime
import pickle
import os.path
from math import floor, ceil
from binascii import hexlify

from inventory import Inventory, File
import compress

# REFERENCE:
# - UPLOAD and RETRIEVA Requests              $0.050 per 1,000 requests
# - LISTVAULTS, GETJOB OUTPUT,
#   DELETE* Request and all other Requests    Free
# - Data Retrievals                           Free
# * Early Deletion Fee (before 90 days)
#   Deletion fee of $0.021 per GB
#   - If you deleted 1GB, 1 month after uploading it: $0.014
#   - If you deleted 1GB, 2 months after uploading:   $0.007


#TODO: Show price of each action.. if it isnt free
#TODO: Show time expected for each action.. if isnt real-time
#TODO: Maybe show message dialog before every request

class App():
    def __init__(self, vault):
        self.vaultName = vault

        self.inventory = None
        self.files = None
        self.active_jobs = []
        self.glacier = boto3.client("glacier")
        self.res = boto3.resource("glacier")
        self.vault = self.res.Vault("-", self.vaultName)
       
        self.root = tk.Tk()
        self.root.title("Amazon Glacier - Support Tool")
        w, h   = 640, 480
        ws, hs = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        x = (ws/2) - (w/2)
        y = (hs/2) - (h/2)
        self.root.geometry("%dx%d+%d+%d" % (w,h,x,y) )

        self.createUI()
        self.updateTick()
        self.root.wm_protocol("WM_DELETE_WINDOW", self.onDelete)
        self.loadDefault()
        self.root.mainloop()

    def onDelete(self):
        if (self.inventory != None):
            fInv = open("inventory.pkl","wb")
            pickle.dump( self.inventory, fInv )
            fInv.close()
        self.root.destroy()

    def loadDefault(self):
        if (os.path.isfile("inventory.pkl")):
            fInv = open("inventory.pkl", "rb")
            self.inventory = pickle.load(fInv)
            self.updateFileList()

    def createUI(self):
        # Add Labels about Vault
        tk.Label(self.root, text="Vault Name: " + self.vault.vault_name).pack()
        tk.Label(self.root, text="Creation Date: " + self.vault.creation_date).pack()
        tk.Label(self.root, text="# of Archives: " + str(self.vault.number_of_archives)).pack()
        tk.Label(self.root, text="Size in bytes: " + str(self.vault.size_in_bytes)).pack()

        # Add Main Buttons
        btns = tk.Frame(self.root)
        tk.Button(btns, text="List Vaults", command=self.listVaults).pack(side=tk.LEFT)
        tk.Button(btns, text="List Files", command=self.listFiles).pack(side=tk.LEFT)
        tk.Button(btns, text="Job Status", command=self.jobStatus).pack(side=tk.LEFT)
        btns.pack()

        # Add File Treeview
        cols = ["File","Size","Date"]
        self._files = ttk.Treeview(self.root, columns=cols, show="headings")
        for c in cols: self._files.heading(c,text=c)
        self._files.pack()

        # Add File Buttons
        tk.Button(self.root, text="Upload Directory", command=self.uploadDirectory).pack()
        tk.Button(self.root, text="Upload File", command=self.uploadFile).pack()
        tk.Button(self.root, text="Multipart File Upload", command=self.uploadFileMP).pack()
        tk.Button(self.root, text="Delete File", command=self.deleteFile).pack()

    def __sha256tree(self, f):
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

    def __sha256treePartial(self, full_data):
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

    def uploadDirectory(self):
        f = filedialog.askdirectory()
        if ( f != () and os.path.isdir(f) ):
            name = os.path.basename(f).replace(".","_")
            n = datetime.datetime.now()
            name = name + n.strftime("-%Y_%m_%d")
            name = name + ".tar.gz"
            print("Compressing Directory into a Temporary File")
            compress.compressDir(name, f)
            self.__uploadFileMP(name)
            os.remove(name)
            print("Removed Temporary Compressed Directory")
            print("Directory Uploaded Successfully")

    def uploadFileMP(self):
        f = filedialog.askopenfilename()
        if ( f != () and os.path.isfile(f) ):
            request = messagebox.askyesno("Multipart Upload","Uploading file in Multiparts: " + f + " ?\nDepending of the size of the file and your bandwidth it may take some time.\nDo you want to continue?")
            if (request): self.__uploadFileMP(f)
    def __uploadFileMP(self, filename):
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
            sha256 = self.__sha256treePartial(data)
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
        sha256 = self.__sha256tree(f)
        archive = multipart.complete(archiveSize=str(last), checksum=sha256)
        print("Upload Completed:",archive)


    def uploadFile(self):
        f = filedialog.askopenfilename()
        if ( f != () and os.path.isfile(f) ):
            request = messagebox.askyesno("Upload File","Uploading file: " + f + " ?\nDepending of the size of the file and your bandwidth it may take some time.\nDo you want to continue?")
            if (request): self.__uploadFile(f)
    def __uploadFile(self, filename):
        # Read File
        f = open(filename,"rb")
        data = f.read()
        comcheck = self.__sha256tree(f)
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
        self.updateFileList()
        
        # Show Window with Result
        top = tk.Toplevel()
        tk.Label(top, text=txtStatus, height=0, width=150).pack()
        tk.Label(top, text="ArchiveId: " + aid, height=0, width=150).pack()
        tk.Label(top, text=checksum, height=0, width=150).pack()
        tk.Label(top, text=comcheck, height=0, width=150).pack()
        #TODO: Do checksum comparison


    def deleteFile(self):
        focus = self._files.focus()
        if (focus == ''): return
        
        # Get Row
        f = self._files.set(focus)
        # Get File
        ffile = self.inventory.getFile(f["Size"], f["Date"], f["File"])
        if (ffile.deleted):
            messagebox.showinfo("File can't be deleted", "File Already Removed from the Cloud")
            return
        
        # Check Interval
        d = dateutil.parser.parse(f["Date"])
        d.replace(tzinfo=None)
        days = (d.replace(tzinfo=None)-datetime.datetime.utcnow()).days
        if (days < 90):
            title = "Continue Deleting Archive?"
            msg = """This file was uploaded less than 90 days ago.
This action will cost deletion fee.
Do you want to continue?"""
            request = messagebox.askyesno(title,msg)

        # Delete?
        if (request and ffile.aid != None and ffile.deleted == False):
            self.glacier.delete_archive(vaultName=self.vaultName, archiveId=ffile.aid)
            print("Deleting....", ffile.aid)
            ffile.deleted = True

        
    def jobStatus(self):
        j = self.glacier.list_jobs(vaultName=self.vaultName)
        print(j)
        top = tk.Toplevel()
        for job in j["JobList"]:
            tk.Label(top, text="Action: " + job["Action"] , height=0, width=50).pack()
            tk.Label(top, text="Status: " + job["StatusCode"] , height=0, width=50).pack()
            tk.Label(top, text="Creation Date: " + job["CreationDate"] , height=0, width=50).pack()
            if (job["StatusCode"] == "Succeeded"):
                tk.Label(top, text="Completion Date: " + job["CompletionDate"] , height=0, width=50).pack()
                jid = job["JobId"]
                print(dateutil.parser.parse(job["CreationDate"]))
                if (job["Action"] == "InventoryRetrieval"):
                    if (self.inventory == None or self.inventory.date < dateutil.parser.parse(job["CreationDate"])):
                        a = self.res.Job("-",self.vaultName, jid)
                        data = a.get_output()["body"]
                        #TODO: Only update inventory if needed. Dont want to lose new/deleted info
                        self.inventory = Inventory( json.loads(data.read().decode("utf-8")) )
                        self.updateFileList()

    def updateFileList(self):
        # Clear Tree
        self._files.delete(*self._files.get_children())
        # Repopulate Tree
        for f in self.inventory.files:
            tags = ()
            if (f.deleted): tags=("deleted",)
            elif (f.isNew): tags=("new",)
            self._files.insert("","end",values=[f.desc,f.size,f.date], tags=tags)
        self._files.tag_configure("deleted", background="red")
        self._files.tag_configure("new", background="green")
    

    def listVaults(self):
        ret = self.glacier.list_vaults()
        if ("VaultList" in ret):
            for i in ret["VaultList"]:
                print(i["VaultName"] + ": " + str(i["SizeInBytes"]) + " bytes")

    def listFiles(self):
        res = boto3.resource("glacier")
        vault = res.Vault("-", self.vaultName)

        request = False
        # Inventory is only created around 1 day after first file is upload
        if (vault.last_inventory_date == None):
            request = messagebox.askyesno("No Inventory Found","Request Inventory from AWS Glacier?\nJob will take around 4-5 hours to complete.")
        else:
            d = dateutil.parser.parse( vault.last_inventory_date )
            d.replace(tzinfo=None)
            days = (datetime.datetime.utcnow() - d.replace(tzinfo=None)).days
            hours = (datetime.datetime.utcnow() - d.replace(tzinfo=None)).seconds/3600.0
            hours = floor(hours*100)/100;
            # Amazon Glacier prepares an inventory for each vault periodically, every 24 hours.
            # When you initiate a job for a vault inventory, Amazon Glacier returns the last
            # inventory for the vault. The inventory data you get might be up to a day or
            # two days old.
            #
            # - So, we only request a new list if our current list is more than 2 days older
            # TODO: Here we need to check if we already have a inventory_retrieval job
            if (days >= 2):
                request = messagebox.askyesno("Inventory is " + str(days) + " days old","Request Inventory from AWS Glacier?\nJob will take around 4-5 hours to complete.")
            else:
                request = messagebox.askyesno("Inventory is " + str(hours) + " hours old","Request Inventory from AWS Glacier?\nJob will take around 4-5 hours to complete.")
                
        if (request):
            a = vault.initiate_inventory_retrieval()
            #TODO: give some kind of feedback
            self.active_jobs.append(a.job_id)
        else:
            # Use old data
            #TODO: Here, update self.inventory with archives information
            # Havent find a way to get old inventory data yet.. so will keep it locally
            print(vault.number_of_archives)
            print(vault.size_in_bytes)
    
    def updateTick(self):
        # Timer in milliseconds
        self.root.after(10000, self.updateTick)
        #print("Tick")
        #for i in reversed( range(len(self.active_jobs)) ):
        #    job = self.jobs[i]
        #    #TODO: However, it is more efficient to use an Amazon SNS
        #    # notification to determine when a job is complete.
        #    if (job.completed):
        #        self.active_jobs.pop(i)
        #        ret = self.glacier.get_job_output()
        #        print(ret)
    

if __name__ == "__main__":
    app = App("GlimchersGroupBackup")
