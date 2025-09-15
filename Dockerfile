FROM node:22-alpine

WORKDIR /usr/src/app

COPY package*.json ./

RUN npm install

COPY . .

# Create shared directories for file uploads and outputs
RUN mkdir -p /usr/src/app/shared/uploads/temp /usr/src/app/shared/outputs

EXPOSE 3000

CMD [ "npm", "start" ]
