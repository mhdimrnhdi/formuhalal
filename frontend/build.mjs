import tailwindcss from '@tailwindcss/postcss';
import autoprefixer from 'autoprefixer';
import fs from 'fs';
import postcss from 'postcss';

async function build() {
  const input = fs.readFileSync('./styles/input.css', 'utf8');
  
  const result = await postcss([
    tailwindcss(),
    autoprefixer
  ]).process(input, {
    from: './styles/input.css',
    to: './dist/styles.css'
  });
  
  fs.mkdirSync('./dist', { recursive: true });
  fs.writeFileSync('./dist/styles.css', result.css);
  console.log(`Built: ${(result.css.length / 1024).toFixed(1)}KB`);
}

build().catch(console.error);