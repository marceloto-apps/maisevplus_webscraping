const winston = require('winston');
const path = require('path');
require('dotenv').config();

const logDir = process.env.LOG_DIR || path.join(__dirname, '../../logs');

const logger = winston.createLogger({
  level: process.env.LOG_LEVEL || 'info',
  format: winston.format.combine(
    winston.format.timestamp({ format: 'YYYY-MM-DD HH:mm:ss' }),
    winston.format.errors({ stack: true }),
    winston.format.json()
  ),
  defaultMeta: { service: 'maisevplus' },
  transports: [
    new winston.transports.File({ filename: path.join(logDir, 'error.log'), level: 'error', maxsize: 5242880, maxFiles: 5 }),
    new winston.transports.File({ filename: path.join(logDir, 'combined.log'), maxsize: 5242880, maxFiles: 5 }),
  ],
});

logger.add(new winston.transports.Console({
  format: winston.format.combine(
    winston.format.colorize(),
    winston.format.simple()
  ),
}));
module.exports = logger;
