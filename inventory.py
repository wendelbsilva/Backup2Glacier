class File():
    def __init__(self, json):
        self.size    = json["Size"]
        self.date    = json["CreationDate"]
        self.desc    = json["ArchiveDescription"]
        self.aid     = json["ArchiveId"]
        self.sha256  = json["SHA256TreeHash"]
        self.deleted = False
    def __str__(self):
        return "File: " + self.desc + " - Size: " + str(self.size) + "bytes - Created: " + self.date
    def __repr__(self):
        return "File: " + self.desc + " - Size: " + str(self.size) + "bytes - Created: " + self.date

class Inventory():
    def __init__(self, json):
        self.arn = json["VaultARN"]
        self.date = json["InventoryDate"]
        self.files = []
        for f in json["ArchiveList"]:
            self.files.append(File(f))

    def __str__(self):
        s  = "Inventory Date: " + self.date + "\n"
        s += str(self.files)
        return s

    def getFile(self, size, date, description):
        ffile = None
        for f in self.files:
            if (str(f.size) == size and f.date == date and f.desc == description): ffile = f
        return ffile
