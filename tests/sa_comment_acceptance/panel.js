"use strict";
const api = typeof browser !== "undefined" ? browser : chrome;
async function status() {
  const result = await api.runtime.sendMessage({action:"status"});
  document.getElementById("status").textContent = result.status;
  document.getElementById("target").textContent = result.target;
  document.getElementById("revision").textContent = result.source_hash;
  document.getElementById("capture").disabled = result.running;
}
document.getElementById("capture").addEventListener("click",async()=>{
  document.getElementById("capture").disabled = true;
  const result = await api.runtime.sendMessage({action:"capture",strategy:document.getElementById("strategy").value});
  await status();
  if (result.error) document.getElementById("status").textContent = result.error;
});
status();
