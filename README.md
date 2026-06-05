# Atlanta Route Planner — Vercel Deployment

This project keeps the frontend as `index.html` and the backend as a Python FastAPI API route under `api/index.py`.

## Files

- `index.html` — static frontend page
- `api/index.py` — Vercel Python FastAPI backend
- `requirements.txt` — Python dependencies for Vercel
- `vercel.json` — routing config
- `.env.example` — environment variable template

## Important Vercel setting

Add this environment variable in Vercel:

```text
MONGO_URI=mongodb+srv://YOUR_USER:YOUR_PASSWORD@YOUR_CLUSTER.mongodb.net/?retryWrites=true&w=majority
```

Optional environment variables:

```text
MONGO_DB=atlanta_tracker
COLLECTION=stop_states
```

## Deploy

```bash
vercel
```

After deployment, open:

```text
https://your-project.vercel.app/api/health
```

You should see `status: ok` when MongoDB is connected.

## Notes

The frontend API base is now `/api`, so all browsers using the Vercel-hosted page read and write the same MongoDB database instead of using only local browser storage.
