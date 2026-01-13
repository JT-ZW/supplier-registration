-- ============================================================
-- Seed Data for Development
-- ============================================================

-- Create initial admin user
-- Password: Admin123! (hashed with argon2)
INSERT INTO admin_users (email, password_hash, full_name, role)
VALUES (
    'admin@procurement.com',
    '$argon2id$v=19$m=65536,t=3,p=4$lzIGgNCak7LWmlPKuVfqfQ$/ZVrWp9o3qny5/ltsyK1S8H3sQnRX7SNAyXZdHy63NU',
    'System Administrator',
    'admin'
);

-- Note: The password hash above is for 'Admin123!'
-- In production, change this immediately after first login
