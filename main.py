#!/usr/bin/python3

import tkinter as tk
import boto3

import hashlib
import os

#TODO: Show price of each action.. if it isnt free
#TODO: Show time expected for each action.. if isnt real-time

glacier = boto3.client("glacier")

def uploadFile(vaultName, filename):
    # Read File
    f = open(filename,"rb")
    data = f.read()
    checksum = hashlib.sha256(data).hexdigest()
    # Upload File
    t = glacier.upload_archive(vaultName=vaultName,archiveDescription=filename,body=data)
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
    

def listVaults():
    ret = glacier.list_vaults()
    if ("VaultList" in ret):
        for i in ret["VaultList"]:
            print(i["VaultName"] + ": " + str(i["SizeInBytes"]) + " bytes")

def listFiles():
    res = boto3.resource("glacier")
    vault = res.Vault("-", "GlimchersGroupBackup")
    print(vault)
    print(vault.last_inventory_date)
    

def test():
    # Test code here
    print("Test")
    
def createUI(rt):
    lstVt = tk.Button(rt, text="List Vaults", command=listVaults)
    lstVt.pack(pady=1, padx=0)   
    lstFl = tk.Button(rt, text="List Files", command=listFiles)
    lstFl.pack(pady=1, padx=20)
    tt = tk.Button(rt, text="test", command=test)
    tt.pack(pady=1, padx=20)    

if __name__ == "__main__":
    root = tk.Tk()
    createUI(root)
    root.mainloop()
