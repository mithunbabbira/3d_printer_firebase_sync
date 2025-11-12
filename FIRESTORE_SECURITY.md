# Firestore Security Rules Setup

## Why Test Mode vs Production Mode?

### Test Mode (Temporary - 30 days)
- **What it does:** Allows anyone to read/write to your database for 30 days
- **Why use it:** Quick setup, no configuration needed to start
- **When to use:** Initial development and testing
- **⚠️ Warning:** After 30 days, Firebase will block all access until you set up rules

### Production Mode (Secure)
- **What it does:** Blocks all access until you define security rules
- **Why use it:** More secure from the start
- **When to use:** When you're ready to deploy or want security from day one
- **Requires:** Setting up security rules immediately

## Recommended Approach

1. **Start with Test Mode** to get the application working quickly
2. **Set up security rules** before the 30-day period expires
3. **Switch to production rules** when ready

## Setting Up Security Rules

### For This Project (Printer Status Sync)

Since this is a **server-side application** (Python script with service account), you have two options:

#### Option 1: Server-Side Only (Recommended)

If only your Python script writes to Firestore (no public dashboard yet):

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Deny all public access
    // Only service account (your Python script) can read/write
    match /{document=**} {
      allow read, write: if false;
    }
  }
}
```

**Why this works:** Your Python script uses the service account key, which bypasses security rules. Only your script can access the database.

#### Option 2: Allow Dashboard Access (For Future)

When you build the dashboard that users will access:

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Printer status - read only for authenticated users
    match /printer_status/{document} {
      allow read: if request.auth != null;  // Any authenticated user can read
      allow write: if false;  // Only service account can write
    }
    
    // Print queue - authenticated users can read, admin can write
    match /print_queue/{document} {
      allow read: if request.auth != null;
      allow write: if request.auth != null && 
                     request.auth.token.admin == true;
    }
    
    // STL uploads - users can read their own, authenticated users can create
    match /stl_uploads/{uploadId} {
      allow read: if request.auth != null && 
                   (resource.data.uploaded_by == request.auth.uid || 
                    request.auth.token.admin == true);
      allow create: if request.auth != null;
      allow update, delete: if request.auth.token.admin == true;
    }
    
    // Deny everything else
    match /{document=**} {
      allow read, write: if false;
    }
  }
}
```

## How to Set Up Rules

1. Go to Firebase Console
2. Select your project
3. Go to **Firestore Database** > **Rules** tab
4. Paste your rules (from above)
5. Click **Publish**

## Testing Your Rules

Use the Firebase Console Rules Simulator:
1. In the Rules tab, click **Rules Playground**
2. Test different scenarios (read/write with different users)

## Important Notes

- **Service Account Keys:** Always bypass security rules - they have admin access
- **Client SDKs:** Must follow security rules
- **Test Mode Expiry:** After 30 days, you MUST have rules set up
- **Best Practice:** Set up rules before deploying to production

## Current Setup (Phase 1)

For now, since you're only running the Python sync script:
- Test mode is fine for initial setup
- The service account key gives your script full access
- Set up proper rules before building the dashboard (Phase 2)

