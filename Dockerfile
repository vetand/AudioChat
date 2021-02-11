FROM python

# set a directory for the app
WORKDIR /usr/src/app

# copy all the files to the container
COPY . .

# install dependencies
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 4750
EXPOSE 4751
EXPOSE 4752

# run the command
CMD ["python", "-u", "./server.py"]
