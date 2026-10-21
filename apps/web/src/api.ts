export async function api<T>(path:string, options:RequestInit={}):Promise<T>{
  const response=await fetch('/api'+path,{credentials:'same-origin',...options,headers:{'Content-Type':'application/json',...options.headers}});
  if(!response.ok){const data=await response.json().catch(()=>({detail:'Unable to reach the service.'}));throw new Error(typeof data.detail==='string'?data.detail:'Please check the form fields and try again.');}
  return response.json();
}
export const money=(minor:number|null)=>minor===null?'Price unverified':new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',maximumFractionDigits:0}).format(minor/100);
export const time=(value:string)=>new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Kolkata',hour:'2-digit',minute:'2-digit'}).format(new Date(value));
export const stamp=(value:string)=>new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Kolkata',day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'}).format(new Date(value))+' IST';
