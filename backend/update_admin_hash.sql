-- Update admin user password hash from bcrypt to argon2
UPDATE admin_users
SET password_hash = '$argon2id$v=19$m=65536,t=3,p=4$lzIGgNCak7LWmlPKuVfqfQ$/ZVrWp9o3qny5/ltsyK1S8H3sQnRX7SNAyXZdHy63NU'
WHERE email = 'admin@procurement.com';
