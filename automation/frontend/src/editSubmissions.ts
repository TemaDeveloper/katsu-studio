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
