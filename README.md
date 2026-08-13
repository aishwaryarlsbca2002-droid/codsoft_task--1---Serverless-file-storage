# Filestore — Serverless Cloud File Storage

A secure, serverless file storage web application built on AWS. Users sign in with Google or email, then upload, download, share, and delete files — with strict per-user access control enforced at the database layer, not just the application layer.

**Live demo:** https://production.d2bq41gc2vr6dq.amplifyapp.com

---

## Features

- 🔐 **Authentication** — Amazon Cognito, supporting both email/password and Google Sign-In (OAuth federation)
- 📤 **Upload / download / delete** — files stored in S3, transferred directly between the browser and S3 via pre-signed URLs (never routed through compute)
- 🔒 **Per-user access control** — every file lookup is scoped to `userId + fileId` together, so one user structurally cannot access another user's files, even if they guess a valid file ID
- ✅ **File validation** — filename and extension checks before an upload is permitted
- 🔗 **Shareable links** — generate a 24-hour public link to any file, no login required to use it
- ⚡ **Fully serverless** — no servers to manage or pay for while idle; scales to zero

---

## Architecture

```
Browser (Amplify-hosted SPA)
      │
      ├── Auth ───────────► Amazon Cognito (User Pool + Google federation)
      │
      ├── API calls ──────► API Gateway (HTTP API, Cognito JWT Authorizer)
      │                            │
      │                            ▼
      │                     AWS Lambda (Python) — one function per action
      │                            │
      │                     ┌──────┴──────┐
      │                     ▼             ▼
      │                  DynamoDB        S3
      │              (file metadata)  (file storage)
      │
      └── Direct file transfer ──► S3 (via pre-signed URLs, bypassing Lambda)
```

**Why this design:**
- **Pre-signed URLs, not Lambda proxying** — Lambda has a small payload limit and routing large files through it is slow and wasteful. Instead, Lambda only ever *grants permission* (a signed, time-limited URL); the actual file bytes travel directly between the browser and S3.
- **DynamoDB alongside S3** — S3 stores files, but has no concept of "who owns this" or "list all of this user's files" beyond prefix scanning. A `userId` + `fileId` composite key in DynamoDB makes both ownership checks and listing fast, and keeps room for future features (tags, soft-delete, share tracking) without touching S3 at all.
- **Ownership enforced at the query, not the app** — every read/delete/share Lambda calls `DynamoDB.get_item(userId, fileId)` together. If the IDs don't both match, there's no result — not a permission check that could be forgotten or coded wrong, but a structural guarantee.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Auth | Amazon Cognito (User Pool, Hosted UI, Google OAuth federation) |
| API | API Gateway (HTTP API) with Cognito JWT Authorizer |
| Compute | AWS Lambda (Python 3.13) |
| Storage | Amazon S3 (pre-signed URLs for upload/download) |
| Database | Amazon DynamoDB (file metadata) |
| Frontend | Vanilla HTML/CSS/JavaScript (no framework, no build step) |
| Hosting | AWS Amplify Hosting (free HTTPS out of the box) |

---

## API Reference

All routes require a valid Cognito JWT in the `Authorization` header (obtained via the Hosted UI login flow), except the resulting `shareUrl`, which is unauthenticated by design.

| Method | Route | Description |
|---|---|---|
| `POST` | `/files` | Request a pre-signed upload URL; creates a metadata record |
| `GET` | `/files` | List all files belonging to the authenticated user |
| `GET` | `/files/{id}` | Get a pre-signed download URL for a specific file (owner-only) |
| `DELETE` | `/files/{id}` | Delete a file's object and its metadata (owner-only) |
| `POST` | `/files/{id}/share` | Generate a 24-hour public share link (owner-only to create) |

---

## Repository Structure

```
filestorage-app/
├── backend/
│   ├── upload_handler.py      # POST /files
│   ├── list_handler.py        # GET /files
│   ├── download_handler.py    # GET /files/{id}
│   ├── delete_handler.py      # DELETE /files/{id}
│   └── share_handler.py       # POST /files/{id}/share
├── frontend/
│   └── index.html             # Single-file SPA — login, upload, file list, actions
├── infrastructure/
│   └── iam-policies/          # Least-privilege IAM policy for each Lambda's role
└── README.md
```

---

## Security Notes

- **Least-privilege IAM** — each Lambda function has its own IAM role, scoped to only the specific S3 actions and DynamoDB table it needs (e.g. the delete function can `DeleteObject`, but cannot `PutObject`). See `infrastructure/iam-policies/`.
- **No public S3 access** — the file storage bucket has all public access blocked. Every file access goes through a Lambda-issued, time-limited, cryptographically signed URL.
- **Ownership isn't assumed, it's queried** — see the architecture note above.
- **CORS is explicitly scoped** — both API Gateway and the S3 bucket only allow requests from this app's specific frontend origin, not `*`.

---

## What I'd Improve With More Time

- Move from a Lambda-writes-both-S3-and-DynamoDB pattern to an **S3 event-driven confirmation** (an S3 trigger flips a file's status from `pending` to `active` only once the upload genuinely completes), removing the current dual-write consistency assumption.
- Deeper file validation post-upload (checking actual file signatures/magic bytes, not just filename extensions).
- A dedicated `share` metadata record (with its own expiry, independent of a fixed pre-signed URL lifetime) to allow revoking a share link early.

---

## Notes on Reproducing This

This repo contains the application code and IAM policy definitions. It does **not** include an infrastructure-as-code template (e.g. CloudFormation/CDK/Terraform) — all AWS resources (S3 buckets, Cognito User Pool, API Gateway, DynamoDB table, Lambda functions) were provisioned manually via the AWS Console as a learning exercise. Bucket names, table names, and endpoint URLs in the code reflect this specific deployment and would need to be updated to redeploy under a different account.
