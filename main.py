#!/usr/bin/python3

import tkinter as tk
import boto3

glacier = boto3.client('glacier')

def listVaults():
    ret = glacier.list_vaults()
    if ("VaultList" in ret):
        for i in ret["VaultList"]:
            print(i["VaultName"] + ": " + str(i["SizeInBytes"]) + " bytes")
    
def createUI(rt):
    btn = tk.Button(rt, text="Press", command=listVaults)
    btn.pack(pady=20, padx=20)

if __name__ == "__main__":  
    root = tk.Tk()
    createUI(root)
    root.mainloop()
