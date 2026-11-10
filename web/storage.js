// Browser drafts follow data-format versions; minor releases share the same keys.
window.storageVersion=1;
function browserStore(native){
 const key=name=>`data-v${window.storageVersion}:${name}`;
 return {
  getItem(name){let value=native.getItem(key(name));if(value===null&&window.storageVersion===1){value=native.getItem(name);if(value!==null)native.setItem(key(name),value)}return value},
  setItem(name,value){native.setItem(key(name),value)},
  removeItem(name){native.removeItem(key(name));if(window.storageVersion===1)native.removeItem(name)}
 };
}
const localData=browserStore(localStorage),sessionData=browserStore(sessionStorage);
