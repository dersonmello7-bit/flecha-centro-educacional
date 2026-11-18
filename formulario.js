document.querySelector('.contact-form')?.addEventListener('submit', function (event) {
  event.preventDefault();
  if (!this.reportValidity()) return;
  const data = new FormData(this);
  const value = (name) => String(data.get(name) || '').trim();
  const message = [
    'Olá! Gostaria de conhecer a Flecha e agendar uma visita.',
    'Responsável: ' + value('responsavel'),
    'Idade da criança: ' + value('idade'),
    value('periodo') ? 'Período de interesse: ' + value('periodo') : '',
    value('mensagem') ? 'Mensagem: ' + value('mensagem') : ''
  ].filter(Boolean).join('\n');
  window.open('https://wa.me/5521982845610?text=' + encodeURIComponent(message),
    '_blank', 'noopener,noreferrer');
});
