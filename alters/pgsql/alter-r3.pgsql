-- update schema to revision 3

ALTER TABLE j2j_users_options ADD disablenotifies boolean DEFAULT false;
