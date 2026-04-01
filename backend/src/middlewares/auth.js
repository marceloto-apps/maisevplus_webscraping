const jwt = require('jsonwebtoken');
const config = require('../config');
const logger = require('../config/logger');
// O User model vai ser carregado no authenticate
const User = require('../models/User');

/**
 * Verifica o Bearer token e injeta req.user resolvido do banco.
 */
const authenticate = async (req, res, next) => {
  try {
    const authHeader = req.headers.authorization;
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return res.status(401).json({
        error: { code: 'UNAUTHORIZED', message: 'Token não fornecido ou formato inválido' }
      });
    }

    const token = authHeader.split(' ')[1];
    
    // Verifica assinatura e expiração
    const decoded = jwt.verify(token, config.jwt.secret);
    
    // Verifica se usuário ainda existe e está ativo
    const user = await User.findById(decoded.id);
    if (!user) {
      return res.status(401).json({
        error: { code: 'UNAUTHORIZED', message: 'Usuário não encontrado' }
      });
    }
    if (!user.is_active) {
      return res.status(403).json({
        error: { code: 'FORBIDDEN', message: 'Conta de usuário inativa' }
      });
    }

    req.user = user;
    next();
  } catch (error) {
    if (error.name === 'TokenExpiredError') {
      return res.status(401).json({
        error: { code: 'TOKEN_EXPIRED', message: 'Token JWT expirado' }
      });
    }
    logger.error('Erro na autenticação JWT:', error);
    return res.status(401).json({
      error: { code: 'UNAUTHORIZED', message: 'Falha na autenticação' }
    });
  }
};

/**
 * Midleware factory para controle de permissões por roles
 * Exemplo: router.post('/sync', authorize('admin'), syncHandler)
 */
const authorize = (...allowedRoles) => {
  return (req, res, next) => {
    if (!req.user || !allowedRoles.includes(req.user.role)) {
      return res.status(403).json({
        error: { code: 'FORBIDDEN', message: 'Acesso negado para este nível de permissão' }
      });
    }
    next();
  };
};

module.exports = { authenticate, authorize };
