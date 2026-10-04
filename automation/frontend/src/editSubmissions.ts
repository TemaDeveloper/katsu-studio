type EditSubmission={key:string;body:string};
type SubmissionStorage=Pick<Storage,'getItem'|'setItem'|'removeItem'>;

export function readEditSubmission(storage:SubmissionStorage,slot:string):EditSubmission|null{
 try{const raw=storage.getItem(slot);if(!raw)return null;const value=JSON.parse(raw);return typeof value.key==='string'&&typeof value.body==='string'?value:null}catch{return null}
}

export function getEditSubmission(storage:SubmissionStorage,slot:string,body:string):EditSubmission{
 const previous=readEditSubmission(storage,slot);
 if(previous?.body===body)return previous;
 const value={key:crypto.randomUUID(),body};
 try{storage.setItem(slot,JSON.stringify(value))}catch{throw new Error('This browser could not save the edit request. Enable browser storage before using AI editing.')}
 return value;
}

export function clearEditSubmission(storage:SubmissionStorage,slot:string){storage.removeItem(slot)}

type ProjectRequest={topic:string;target_seconds:number;budget_usd:number};

export function readProjectSubmission(storage:SubmissionStorage,slot:string):EditSubmission|null{
 const saved=readEditSubmission(storage,slot);
 if(!saved)return null;
 try{const data=JSON.parse(saved.body);return typeof data.topic==='string'&&Number.isFinite(data.target_seconds)?saved:null}catch{return null}
}

export function getProjectSubmission(storage:SubmissionStorage,slot:string,request:ProjectRequest):EditSubmission{
 const previous=readProjectSubmission(storage,slot);
 if(previous){
  const data=JSON.parse(previous.body);
  // An older browser may have already created a project before losing its response.
  // Reuse that exact body and key, even if it included the retired count field.
  if(data.topic===request.topic&&data.target_seconds===request.target_seconds&&data.budget_usd===request.budget_usd)return previous;
 }
 const value={key:crypto.randomUUID(),body:JSON.stringify(request)};
 try{storage.setItem(slot,JSON.stringify(value))}catch{throw new Error('This browser could not save your video request. Enable browser storage before starting production.')}
 return value;
}
