from config import config
import pgdb

class database:
    def __init__(self):
        self.db=pgdb.connect(host=config.DB_HOST,user=config.DB_USER,password=config.DB_PASS,database=config.DB_NAME)
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
        return self.dbCursor.fetchone()

    def fetchall(self,query):
        self.dbCursor.execute(query)
        return self.dbCursor.fetchall()

    def execute(self,query):
        self.dbCursor.execute(query)

    def commit(self):
        self.db.commit()

    def getIdByJid(self,qjid):
        a=self.fetchone("SELECT id from "+self.dbTablePrefix+"users WHERE jid='"+self.dbQuote(qjid.encode("utf-8"))+"'")
        if a==None:
            return a
        return a[0]

    def getDataById(self,uid):
        return self.fetchone("SELECT username,password,server,domain,port from "+self.dbTablePrefix+"users WHERE id="+str(uid))

    def getOptsById(self,uid):
        return self.fetchone("SELECT replytext,lightnotify,autoreplybutforward,onlyroster,autoreplyenabled from "+self.dbTablePrefix+"users_options WHERE id="+str(uid))