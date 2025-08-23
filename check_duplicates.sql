SELECT username, COUNT(*) as count FROM profiles GROUP BY username HAVING count > 1;
