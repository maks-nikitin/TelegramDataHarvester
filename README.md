Installation and Setup
1. Environment Preparation
Clone the repository and install the required dependencies:
git clone https://github.com/maks-nikitin/TelegramDataHarvester.git
cd TelegramDataHarvester
pip install -r requirements.txt
2. API Access Configuration
To use the parser, you need to obtain an API_ID and API_HASH from the my.telegram.org website.
Create a .env file in the root directory and add your credentials:
API_ID=your_api_id
API_HASH=your_api_hash
3. Running the Application
Launch the web interface using the following command:
streamlit run src/ui/app.py