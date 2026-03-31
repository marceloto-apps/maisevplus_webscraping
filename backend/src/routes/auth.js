const express = require('express');
const router = express.Router();
const Joi = require('joi');
const jwt = require('jsonwebtoken');
const rateLimit = require('express-rate-limit');
const { User } = require('../models');
const config = require('../config');
const { validate } = require('../middlewares/validate');
const AppError = require('../utils/AppError');

const registerSchema = Joi.object({
  username: Joi.string().alphanum().min(3).max(30).required(),
  email: Joi.string().email().required(),
  password: Joi.string().min(6).required(),
});

const loginSchema = Joi.object({
  email: Joi.string().email().required(),
  password: Joi.string().required(),
});

// Helper pra geração estática do JWT
const generateToken = (user) => {
  if (!config.jwt.secret) {
    throw new AppError('JWT_SECRET não configurado no ambiente', 500);
  }
  return jwt.sign(
    { id: user.id, role: user.role, username: user.username },
    config.jwt.secret,
    { expiresIn: config.jwt.expiresIn }
  );
};

router.post('/register', validate(registerSchema), async (req, res, next) => {
  try {
    const { username, email, password } = req.body;

    // Conflitos de Conta
    const existingUser = await User.findByEmail(email);
    if (existingUser) throw new AppError('Email já está em uso', 400);

    const existingUsername = await User.findByUsername(username);
    if (existingUsername) throw new AppError('Username já está em uso', 400);

    // Salva model (já embute bcrypt na model layer)
    const newUser = await User.create({ username, email, password });
    
    // Auto-login após register entregando token
    const token = generateToken(newUser);

    res.status(201).json({
      user: { id: newUser.id, username: newUser.username, role: newUser.role },
      token
    });
  } catch (err) {
    next(err);
  }
});

const loginLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 10, // Trava Brute Force
  message: { status: 'error', message: 'Muitas tentativas de login bloqueadas. Tente novamente em 15 minutos.' }
});

router.post('/login', loginLimiter, validate(loginSchema, 'body'), async (req, res, next) => {
  try {
    const { email, password } = req.body;

    const user = await User.findByEmail(email);
    if (!user) {
      throw new AppError('Credenciais inválidas', 401, 'UNAUTHORIZED');
    }

    const isValid = await User.validatePassword(password, user.password_hash);
    if (!isValid) {
      throw new AppError('Credenciais inválidas', 401, 'UNAUTHORIZED');
    }

    if (!user.active) {
      throw new AppError('Usuário inativo ou bloqueado', 403, 'FORBIDDEN');
    }

    const token = generateToken(user);
    
    res.json({
      user: { id: user.id, username: user.username, role: user.role },
      token
    });
  } catch (err) {
    next(err);
  }
});

module.exports = router;
