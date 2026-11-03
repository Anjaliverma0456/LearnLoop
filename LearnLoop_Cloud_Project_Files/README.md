# LearnLoop Cloud
A cloud-ready study resource management platform based on the submitted synopsis.

## Features
- Student registration/login (password hashes)
- Create and delete subject collections
- Save learning links and upload study documents
- Track completed/pending resources and dashboard progress
- Toggle resource sharing
- Responsive dashboard UI

## Run locally
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000 and create an account.

## Deployment
The app includes a Dockerfile and Procfile for container/PaaS deployment. For IBM Cloud Code Engine:
1. Create an IBM Cloud account and a Code Engine project.
2. Build/deploy the container from this repository (or build locally and push to IBM Container Registry).
3. Set `SECRET_KEY` to a long random value.
4. Attach persistent storage for `DATABASE_PATH` and `UPLOAD_FOLDER`, or configure IBM Cloudant and IBM Cloud Object Storage adapters before production use.
5. Verify the deployed URL and authentication flows.

**Cloud note:** The current runnable mini-project uses SQLite and local upload storage as a reliable demo baseline. The synopsis proposes IBM Cloudant and IBM Cloud Object Storage; those services require account setup/credentials and are not automatically connected in this package. Avoid claiming these integrations are active until configured.
