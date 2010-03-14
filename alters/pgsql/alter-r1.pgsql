-- update schema to revision 1

ALTER TABLE j2j_users DROP CONSTRAINT j2j_users_id_key;
ALTER TABLE j2j_users ADD PRIMARY KEY(id);

ALTER TABLE j2j_rosters DROP CONSTRAINT j2j_rosters_num_key;
ALTER TABLE j2j_rosters DROP num;
ALTER TABLE j2j_rosters RENAME id TO user_id;

CREATE INDEX j2j_roster_user_id_index ON "j2j_rosters"("user_id");
CREATE INDEX j2j_roster_item_index ON "j2j_rosters"("user_id", "jid");

ALTER TABLE j2j_users_options DROP CONSTRAINT j2j_users_options_id_key;
ALTER TABLE j2j_users_options RENAME id TO user_id;
ALTER TABLE j2j_users_options ADD CONSTRAINT j2j_users_id FOREIGN KEY ("user_id") REFERENCES "j2j_users" ("id") DEFERRABLE INITIALLY DEFERRED;

CREATE INDEX j2j_users_options_user_id ON "j2j_users_options" ("user_id");
