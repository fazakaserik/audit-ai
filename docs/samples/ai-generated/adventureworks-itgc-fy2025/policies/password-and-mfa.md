# Password and Multi-Factor Authentication Standard

**Standard ID:** AW-STD-AUTH-2025  
**Parent policy:** AW-ISP-2025  
**Effective:** 1 January 2025

## Password requirements (interactive accounts)

| Requirement | Value |
|-------------|-------|
| Minimum length | 14 characters |
| Complexity | Passphrase encouraged; blocked common passwords via banned-list |
| Maximum age | 365 days (with MFA); 90 days for accounts without MFA (legacy only — none remaining) |
| History | Last 24 passwords |
| Lockout | 10 failed attempts / 15-minute soft lock |

## Multi-factor authentication

**MFA is required for all workforce remote access** (VPN, SSO web apps, email from untrusted networks). MFA is also required for:

- All privileged / administrator roles (including cloud consoles);
- All access to systems processing Restricted data;
- Contractor accounts with Corporate network access.

Accepted MFA factors: phishing-resistant hardware key (preferred), platform authenticator, or TOTP app. SMS OTP is prohibited for privileged roles and discouraged for all users (sunset by 30 June 2025).

## Service accounts

Interactive logon disabled. Credentials stored in the enterprise secrets vault with automated rotation ≤ 60 days unless certificate-based authentication is used.
