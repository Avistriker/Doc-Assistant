# generate_and_save_key.py
import secrets
import os

def generate_and_save_key():
    key = secrets.token_urlsafe(32)
    
    # Create .env file if doesn't exist
    env_file = '.env'
    
    if os.path.exists(env_file):
        # Read existing .env
        with open(env_file, 'r') as f:
            lines = f.readlines()
        
        # Update SECRET_KEY
        with open(env_file, 'w') as f:
            for line in lines:
                if line.startswith('SECRET_KEY='):
                    f.write(f'SECRET_KEY={key}\n')
                else:
                    f.write(line)
    else:
        # Create new .env with key
        with open(env_file, 'w') as f:
            f.write(f'SECRET_KEY={key}\n')
            f.write('FLASK_DEBUG=True\n')
            f.write('FLASK_PORT=5000\n')
    
    print(f"✅ Secret key generated and saved to {env_file}")
    print(f"📋 Add this to your deployment environment:")
    print(f"SECRET_KEY={key}")

if __name__ == "__main__":
    generate_and_save_key()