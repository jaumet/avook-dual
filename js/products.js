const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
const PAYPAL_ACTION_URL = isLocalhost
  ? 'https://www.sandbox.paypal.com/cgi-bin/webscr'
  : 'https://www.paypal.com/cgi-bin/webscr';

const API_BASE_URL = window.__AVOOK_API_BASE__;
const PAYPAL_NOTIFY_URL = `${API_BASE_URL}/webhooks/paypal`;

function formatPrice(value){
  if(typeof value !== 'number') return '';
  return value.toLocaleString('ca-ES', { style:'currency', currency:'EUR' });
}

async function loadProducts(){
  const grid = document.getElementById('productsGrid');
  grid.innerHTML = '';
  try {
    const res = await fetch('./catalog/packages.json');
    const data = await res.json();
    const packages = (data.packages || [])
      .filter(pkg => !pkg.is_free)
      .filter(pkg => pkg.paypal_button_id);

    packages.forEach(pkg => grid.appendChild(renderCard(pkg)));
  } catch (err){
    const p = document.createElement('p');
    p.textContent = 'No s\'han pogut carregar els productes. Torna-ho a provar més tard.';
    grid.appendChild(p);
  }
}

function renderCard(pkg){
  const card = document.createElement('article');
  card.className = 'product-card';

  const title = document.createElement('h3');
  title.textContent = pkg.name;
  card.appendChild(title);

  const level = document.createElement('p');
  level.className = 'product-level';
  level.textContent = `Nivell: ${pkg.level_range}`;
  card.appendChild(level);

  if(pkg.description){
    const desc = document.createElement('p');
    desc.textContent = pkg.description;
    desc.className = 'product-desc';
    card.appendChild(desc);
  }

  if(pkg.title_ids?.length){
    const list = document.createElement('ul');
    list.className = 'product-list';
    pkg.title_ids.slice(0,5).forEach(id => {
      const li = document.createElement('li');
      li.textContent = id.replace(/-/g,' ');
      list.appendChild(li);
    });
    card.appendChild(list);
  }

  if(pkg.price_eur){
    const price = document.createElement('p');
    price.className = 'product-price';
    price.textContent = formatPrice(pkg.price_eur);
    card.appendChild(price);
  }

  card.appendChild(buildPaypalForm(pkg));
  return card;
}

function buildPaypalForm(pkg){
  const form = document.createElement('form');
  form.action = PAYPAL_ACTION_URL;
  form.method = 'post';
  form.target = '_blank';
  form.className = 'paypal-form';
  form.innerHTML = `
    <input type="hidden" name="cmd" value="_s-xclick">
    <input type="hidden" name="hosted_button_id" value="${pkg.paypal_button_id}">
    <input type="hidden" name="notify_url" value="${PAYPAL_NOTIFY_URL}">
    <input type="hidden" name="custom" value="${pkg.id}">
    <button type="submit" class="paypal-btn">Paga amb PayPal</button>
  `;
  return form;
}

function setupModal(){
  const modal=document.getElementById('infoModal');
  const openBtn=document.getElementById('infoBtn');
  const closeBtn=document.getElementById('closeModal');
  if(!modal||!openBtn||!closeBtn) return;
  openBtn.onclick=()=>modal.style.display='flex';
  closeBtn.onclick=()=>modal.style.display='none';
  window.onclick=e=>{if(e.target==modal)modal.style.display='none';};
}

function setupThemeToggle(){
  const themeBtn=document.getElementById('themeBtn');
  if(!themeBtn) return;
  themeBtn.onclick=()=>{
    document.body.classList.toggle('light');
    const isLight=document.body.classList.contains('light');
    themeBtn.textContent=isLight?'🌙 Fosc':'☀️ Clar';
  };
}

setupModal();
setupThemeToggle();
loadProducts();
