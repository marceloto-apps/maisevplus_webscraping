const AppError = require('./AppError');

const parseId = (value, label = 'ID') => {
  const id = parseInt(value, 10);
  if (isNaN(id)) throw new AppError(`${label} inválido`, 400);
  return id;
};

module.exports = parseId;
