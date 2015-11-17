#!/usr/bin/python3

import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
import boto3

import hashlib
import os
import dateutil.parser
import json
import datetime
import pickle
import os.path

from inventory import Inventory

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
        tk.Button(self.root, text="Delete File", command=self.deleteFile).pack()


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
                if (job["Action"] == "InventoryRetrieval"):
                    a = self.res.Job("-",self.vaultName, jid)
                    data = a.get_output()["body"]
                    self.inventory = Inventory( json.loads(data.read().decode("utf-8")) )
                    self.updateFileList()

    def updateFileList(self):
        # Clear Tree
        self._files.delete(*self._files.get_children())
        # Repopulate Tree
        for f in self.inventory.files:
            tags = ()
            if (f.deleted): tags=("deleted",)
            self._files.insert("","end",values=[f.desc,f.size,f.date], tags=tags)
        self._files.tag_configure("deleted", background="red")

    def uploadFile(self, filename):
        # Read File
        f = open(filename,"rb")
        data = f.read()
        checksum = hashlib.sha256(data).hexdigest()
        # Upload File
        t = self.glacier.upload_archive(vaultName=self.vaultName,archiveDescription=filename,body=data)
        # Show Window with Result
        top = tk.Toplevel()
        for i in t["ResponseMetadata"]:
            txt = i + ": " + str(t["ResponseMetadata"][i])
            lbl = tk.Label(top, text=txt, height=0, width=150)
            lbl.pack()
            
        for i in t:
            if (i != "ResponseMetadata"):
                txt = i + ": " + str(t[i])
                lbl = tk.Label(top, text=txt, height=0, width=80, wraplength=600, justify="left")
                lbl.pack()
    

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
            # Amazon Glacier prepares an inventory for each vault periodically, every 24 hours.
            # When you initiate a job for a vault inventory, Amazon Glacier returns the last
            # inventory for the vault. The inventory data you get might be up to a day or
            # two days old.
            #
            # - So, we only request a new list if our current list is more than 2 days older
            if (days > 2):
                # TODO: Here we need to check if we already have a inventory_retrieval job
                request = messagebox.askyesno("Inventory " + str(days) + " days old","Request Inventory from AWS Glacier?\nJob will take around 4-5 hours to complete.")
                
        if (request):
            a = vault.initiate_inventory_retrieval()
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
