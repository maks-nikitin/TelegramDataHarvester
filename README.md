Installation and Setup
!!!Important Notice
Telegram Account Safety: It is highly recommended to use a secondary or non-essential phone number for this application. While Telegram does not ban users simply for using the MTProto library, your account may be restricted or banned for violating Telegram's Terms of Service (e.g., aggressive data harvesting, suspicious activity, or spam). Use this tool responsibly and at your own risk.
Prerequisites: You must have a working Telegram account and the Telegram app installed on your phone/PC to receive the authorization code.
1. Environment Preparation
Clone the repository and install the required dependencies:
2. API Access Configuration
-To interact with Telegram's servers, you need to obtain your own API credentials:
-Go to my.telegram.org and log in.
-Go to "API development tools" and create a new application.
-Copy your API_ID and API_HASH.
-Create a .env file in the root directory of the project and add your credentials:
3. Account Authentication (First-time setup)
Before launching the main application, you must create a session file. This step links the app to your Telegram account:
-Run the initialization script:
python test_api.py
-In the console: Enter your phone number (including country code).
-In your Telegram app: You will receive a login code.
-In the console: Enter the received code.
Once completed, a .session file will be created in the data/ folder, and you won't need to repeat this step again.
4. Running the Application
streamlit run src/ui/app.py