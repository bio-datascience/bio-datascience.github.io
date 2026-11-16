// Reveal contact details only after a visitor explicitly requests them.
// This deters basic address harvesting; it is not protection against advanced bots.
document.querySelectorAll('button[data-contact]').forEach(button=>{
 button.addEventListener('click',()=>{
  const contact=JSON.parse(atob(button.dataset.contact));
  const anchor=document.createElement('a');
  anchor.href='mail'+'to:'+contact.address+(contact.query?'?'+contact.query:'');
  anchor.textContent=contact.address;
  anchor.className='revealed-email';
  button.replaceWith(anchor);
  anchor.focus();
 },{once:true});
});
