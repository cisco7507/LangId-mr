const tailwindPostcss = require('@tailwindcss/postcss');

module.exports = {
  plugins: [
    tailwindPostcss(),
    require('autoprefixer')(),
  ],
};
