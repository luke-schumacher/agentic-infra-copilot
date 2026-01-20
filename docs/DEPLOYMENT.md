# Deployment & Sharing Guide

This guide outlines how to share your **Agentic Infra Co-Pilot** with others. 

Choose the method that best fits your needs:
1.  **Quick Demo (Tunneling):** Best for showing friends/clients instantly without setting up a server.
2.  **Permanent Hosting (VPS):** Best for a portfolio or production environment running 24/7.

---

## Option 1: The "Local Tunnel" (Best for Demos)

If you just want to show this to a friend, professor, or client *right now* without configuring a cloud server, use a **Tunnel**. 

**How it works:** You run the heavy code (Docker containers) on your powerful laptop, but use a tool to give the world a public URL (e.g., `https://myapp.share.zrok.io`) that routes traffic securely to your computer.

### Prerequisites
*   The application must be running locally.
*   Your `.env` file stays safely on your laptop; no need to upload it anywhere.

### Steps

1.  **Start the App Locally**
    Ensure your Docker containers are up and running:
    ```bash
    docker-compose up -d
    ```
    Verify you can access the UI at `http://localhost:8501`.

2.  **Install a Tunneling Tool**
    We recommend **zrok** (open source/free) or **ngrok**.

    *   **zrok:** Follow instructions at [zrok.io](https://zrok.io/).
    *   **ngrok:** Download from [ngrok.com](https://ngrok.com/).

3.  **Share the Port**
    Run the following command in your terminal to expose your Streamlit UI (port 8501):

    **Using zrok:**
    ```bash
    zrok share public localhost:8501
    ```

    **Using ngrok:**
    ```bash
    ngrok http 8501
    ```

4.  **Share the URL**
    The tool will generate a public URL (e.g., `https://xyz.share.zrok.io`).
    *   Send this link to anyone.
    *   They can access your Streamlit UI and interact with the agents as if it were hosted on a server.
    *   **Note:** The link only works as long as your laptop is on and the command is running.

---

## Option 2: Virtual Private Server (Best for Permanent Hosting)

If you want the application to be online 24/7 without relying on your laptop, you should deploy it to a Virtual Private Server (VPS).

**Recommended Providers:**
*   **Oracle Cloud (Free Tier):** Highly recommended. Their "Always Free" ARM Ampere instances (4 OCPUs, 24GB RAM) are powerful enough to run Neo4j + 3 Agents + UI for free.
*   **DigitalOcean / Hetzner / AWS:** Paid options (approx. $10-20/month for sufficient RAM).

### Steps

1.  **Provision the Server**
    *   Create an Ubuntu Linux instance (VM) with your cloud provider.
    *   Ensure you allow inbound traffic on ports `8501` (Streamlit) and `8001-8003` (APIs) in the firewall settings.

2.  **Install Docker on the Server**
    SSH into your server and run:
    ```bash
    # Update and install Docker
    sudo apt-get update
    sudo apt-get install -y docker.io docker-compose
    
    # Start Docker
    sudo systemctl start docker
    sudo systemctl enable docker
    ```

3.  **Clone the Repository**
    ```bash
    git clone https://github.com/YOUR_USERNAME/agentic-infra-copilot.git
    cd agentic-infra-copilot
    ```

4.  **Securely Add Secrets**
    **Critical:** Do not upload your `.env` file to GitHub. Instead, recreate it on the server:
    
    ```bash
    nano .env
    ```
    
    Paste your production secrets into this file:
    ```properties
    GROQ_API_KEY=gsk_...
    NEO4J_PASSWORD=secure_password
    # ... any other keys
    ```
    Press `Ctrl+X`, then `Y`, then `Enter` to save.

5.  **Run the System**
    ```bash
    sudo docker-compose up -d --build
    ```

6.  **Access**
    Your app is now live at `http://YOUR_SERVER_IP:8501`.

---

## Security Note regarding `.env`

*   **Never commit your `.env` file to Git.**
*   Ensure your `.gitignore` file includes `.env`.
*   When sharing code, provide a `.env.example` file with placeholder values so others know which variables to configure.
