# Part of J2J (http://JRuDevels.org)
# Copyright 2007 JRuDevels.org

import config
config=config.config()

__id__ = "$Id$"

class database:
    def __init__(self):
        if config.DB_TYPE == "mysql":
            exec 'import MySQLdb'
            self.db=MySQLdb.connect(host=config.DB_HOST,user=config.DB_USER,passwd=config.DB_PASS,db=config.DB_NAME)
        elif config.DB_TYPE == "postgres":
            exec 'import pgdb'
            self.db=pgdb.connect(host=config.DB_HOST,user=config.DB_USER,password=config.DB_PASS,database=config.DB_NAME)
        else:
            self.db = None
        self.dbCursor=self.db.cursor()
        self.dbTablePrefix=config.DB_PREFIX

    def __del__(self):
        if self.dbCursor:
            self.dbCursor.close()
        if self.db:
            self.db.close()

    def dbQuote(self,string):
        return string.replace("\\","\\\\").replace("'","\\'")

    def fetchone(self,query):
        self.dbCursor.execute(query)
        data = self.dbCursor.fetchone()
        if data == None:
            return data
        return list(data)

    def fetchall(self,query):
        self.dbCursor.execute(query)
        return self.dbCursor.fetchall()

    def execute(self,query):
        self.dbCursor.execute(query)

    def commit(self):
        self.db.commit()

    def getCount(self,table,where=None):
        if where==None:
            where=''
        else:
            where="WHERE "+where
        return self.fetchone("SELECT count(*) FROM %s %s" % (self.dbTablePrefix+table,where))[0]

    def getIdByJid(self,qjid):
        a=self.fetchone("SELECT id from "+self.dbTablePrefix+"users WHERE jid='"+self.dbQuote(qjid.encode("utf-8"))+"'")
        if a==None:
            return a
        return a[0]

    def getDataById(self,uid):
        return self.fetchone("SELECT username,password,server,domain,port from "+self.dbTablePrefix+"users WHERE id="+str(uid))

    def getOptsById(self,uid):
        data=self.fetchone("SELECT replytext,lightnotify,autoreplybutforward,onlyroster,autoreplyenabled from "+self.dbTablePrefix+"users_options WHERE id="+str(uid))
        if data[0]==None:
            data[0]=''
        return data