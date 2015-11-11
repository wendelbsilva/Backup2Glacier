#!/usr/bin/python3

import tkinter as tk
import boto3

import hashlib
import os
import dateutil.parser

#TODO: Show price of each action.. if it isnt free
#TODO: Show time expected for each action.. if isnt real-time

class App():
    def __init__(self, vault):       
        self.vaultName = vault
        
        self.active_jobs = []
        self.glacier = boto3.client("glacier")
        self.res = boto3.resource("glacier")
        self.vault = self.res.Vault("-", self.vaultName)
       
        self.root = tk.Tk()
        self.root.title("Title")
        w, h   = 640, 480
        ws, hs = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        x = (ws/2) - (w/2)
        y = (hs/2) - (h/2)
        self.root.geometry("%dx%d+%d+%d" % (w,h,x,y) )
        
        print(dir(self.root))
        self.createUI()
        self.updateTick()
        self.root.mainloop()

    def createUI(self):
        tk.Label(self.root, text="Vault Name: " + self.vault.vault_name).pack()
        tk.Label(self.root, text="Creation Date: " + self.vault.creation_date).pack()
        tk.Label(self.root, text="# of Archives: " + str(self.vault.number_of_archives)).pack()
        tk.Label(self.root, text="Size in bytes: " + str(self.vault.size_in_bytes)).pack()

        btns = tk.Frame(self.root)
        tk.Button(btns, text="List Vaults", command=self.listVaults).pack(side=tk.LEFT)
        tk.Button(btns, text="List Files", command=self.listFiles).pack(side=tk.LEFT)
        tk.Button(btns, text="Job Status", command=self.jobStatus).pack(side=tk.LEFT)
        btns.pack()

        
    def jobStatus(self):
        j = self.glacier.list_jobs(vaultName=self.vaultName)
        top = tk.Toplevel()
        for job in j["JobList"]:
            tk.Label(top, text="Action: " + job["Action"] , height=0, width=50).pack()
            tk.Label(top, text="Status: " + job["StatusCode"] , height=0, width=50).pack()
            tk.Label(top, text="Date  : " + job["CreationDate"] , height=0, width=50).pack()
        print(j)

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
        
        # Inventory is only created around 1 day after first file is upload
        if (vault.last_inventory_date != None):
            d = dateutil.parser.parse( vault.last_inventory_date )
            d.replace(tzinfo=None)
            days = (d.replace(tzinfo=None)-datetime.datetime.utcnow()).days

            # Amazon Glacier prepares an inventory for each vault periodically, every 24 hours.
            # When you initiate a job for a vault inventory, Amazon Glacier returns the last
            # inventory for the vault. The inventory data you get might be up to a day or
            # two days old.
            #
            # - So, we only request a new list if our current list is more than 2 days older
            if (days > 2):
                # TODO: Here we need to check if we already have a inventory_retrieval job
                a = vault.initiate_inventory_retrieval()
                active_jobs.append(a.job_id)
            else:
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
