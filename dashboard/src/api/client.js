import axios from 'axios';

const client = axios.create({
  baseURL: 'https://1ltnq33e02.execute-api.us-east-1.amazonaws.com/api',
  timeout: 5000,
});

export default client;
