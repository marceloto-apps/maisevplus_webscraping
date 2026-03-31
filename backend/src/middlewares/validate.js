/**
 * Factory middleware para validar req.body, req.query, ou req.params usando Joi
 * Exemplo de uso: validate(schemaBody) -> defaulta para req.body
 */
const validate = (schema, source = 'body') => {
  return (req, res, next) => {
    const { error, value } = schema.validate(req[source], {
      abortEarly: false, // retorna todos os erros
      stripUnknown: true // remove chaves extras não declaradas
    });

    if (error) {
      const details = error.details.map(err => ({
        field: err.path.join('.'),
        message: err.message
      }));
      
      return res.status(400).json({
        error: {
          code: 'VALIDATION_ERROR',
          message: 'Dados de entrada inválidos',
          details
        }
      });
    }

    // Sobrescreve com os dados validados (incluindo defaults do Joi)
    req[source] = value;
    next();
  };
};

module.exports = { validate };
