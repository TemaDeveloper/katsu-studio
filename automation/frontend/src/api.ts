export async function api<T>(path:string, options:RequestInit={}):Promise<T> {
  const response=await fetch('/api'+path,{...options,headers:{'Content-Type':'application/json',...options.headers}});
  if(!response.ok){const data=await response.json().catch(()=>({}));throw new Error(typeof data.detail==='string'?data.detail:'Please check the entered values and try again.');}
  return response.json();
}
export const fileUrl=(id:string,kind:string,download=false)=>`/api/projects/${id}/artifacts/${kind}${download?'?download=true':''}`;
export const runtime=(seconds:number|null)=>seconds===null?'Timing pending':`${Math.floor(seconds/60)}:${String(Math.round(seconds%60)).padStart(2,'0')}`;
export const statusName=(status:string)=>({queued:'Waiting',running:'In production',needs_attention:'Needs attention',cancelled:'Stopped',completed:'Ready to watch'}[status]??status);
