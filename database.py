# Part of J2J (http://JRuDevels.org)
# Copyright 2007 JRuDevels.org

__id__ = "$Id$"

class Database:
    def __init__(self,config):
        self.config = config
        if self.config.DB_TYPE == "mysql":
            exec 'import MySQLdb'
            self.db = MySQLdb.connect(host=self.config.DB_HOST,
                                      user=self.config.DB_USER,
                                      passwd=self.config.DB_PASS,
                                      db=self.config.DB_NAME)
        elif self.config.DB_TYPE == "postgres":
            exec 'import pgdb'
            self.db = pgdb.connect(host=self.config.DB_HOST,
                                   user=self.config.DB_USER,
                                   password=self.config.DB_PASS,
                                   database=self.config.DB_NAME)
        else:
            self.db = None
        self.dbCursor = self.db.cursor()
        self.dbTablePrefix = self.config.DB_PREFIX

    def __del__(self):
        if self.dbCursor:
            self.dbCursor.close()
        if self.db:
            self.db.close()

    def dbQuote(self, string):
        return string.replace("\\", "\\\\").replace("'", "\\'")

    def fetchone(self, query):
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

    def getCount(self, table, where=None):
        if where == None:
            where = ''
        else:
            where = "WHERE " + where
        return self.fetchone("SELECT count(*) FROM %s %s" % \
                             (self.dbTablePrefix + table, where))[0]

    def getIdByJid(self, qjid):
        a = self.fetchone("SELECT id from " + self.dbTablePrefix + \
                          "users WHERE jid='" + \
                          self.dbQuote(qjid.encode("utf-8")) + "'")
        if a == None:
            return a
        return a[0]

    def getDataById(self, uid):
        return self.fetchone("SELECT username,password,server,\
                              domain,port,import_roster,\
                              remove_from_guest_roster from " + \
                              self.dbTablePrefix + "users WHERE id=" + str(uid))

    def getOptsById(self, uid):
        data = self.fetchone("SELECT replytext,lightnotify,\
                                     autoreplybutforward,onlyroster,\
                                     autoreplyenabled from " + \
                                     self.dbTablePrefix + \
                                     "users_options WHERE user_id=" + str(uid))
        if data[0] == None:
            data[0] = ''
        return data
