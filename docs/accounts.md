# Local demonstration accounts

These public demo credentials are deliberately seeded for local evaluation. Do not expose the demo deployment publicly with these passwords.

| Role | Name | Email | Password |
|---|---|---|---|
| Admin | RouteRescue Admin | admin@routerescue.local | Admin@12345 |
| User | Aarav Sharma | aarav@routerescue.local | Aarav@12345 |
| User | Diya Patel | diya@routerescue.local | Diya@12345 |
| User | Kabir Rao | kabir@routerescue.local | Kabir@12345 |
| User | Meera Nair | meera@routerescue.local | Meera@12345 |

Each traveller starts with two trips. Budgets and ranking preferences differ between accounts. Accounts and assignments are created once at startup; existing passwords, account status, inventory and trips are not overwritten.

The admin dashboard can inspect users/trips/recovery runs, disable or enable users, and update per-trip demo fares, capacity and availability. Updating an offer increments its version, supersedes old recovery results and prevents stale confirmation.

Passwords use salted scrypt hashes. Browser cookies contain random revocable session tokens; only their SHA-256 hashes are stored. Sessions expire after 12 hours. Logout and account disable revoke sessions. Repeated failed login attempts are throttled. Users cannot read other users' trips or access admin APIs.
