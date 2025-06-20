FROM python:3.12-slim
 
# Set working directory
WORKDIR /app
 
# Install dependencies first (for better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
 

 
# Copy application files
COPY run.py .
COPY .env .
COPY app .
 


EXPOSE 5000
 
# Command to run the application using port 4001
CMD ["python", "run.py"]
 
 