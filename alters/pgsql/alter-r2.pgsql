-- update schema to revision 2

ALTER TABLE j2j_users ADD CONSTRAINT j2j_users_jid_key UNIQUE (jid);
