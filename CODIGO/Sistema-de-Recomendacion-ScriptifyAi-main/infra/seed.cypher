MATCH (n) DETACH DELETE n;
CREATE (:Topic {name:"fitness"}), (:Topic {name:"tecnologia"}), (:Topic {name:"marketing"});
CREATE (:Video {id:"vid1", title:"Rutina HIIT 15 min", format:"short", retention:0.52, ctr:0.07}),
       (:Video {id:"vid2", title:"Movilidad de hombro", format:"short", retention:0.46, ctr:0.06}),
       (:Video {id:"vid3", title:"Core principiantes", format:"short", retention:0.49, ctr:0.05}),
       (:Video {id:"vid4", title:"Top 5 herramientas IA", format:"short", retention:0.55, ctr:0.09}),
       (:Video {id:"vid5", title:"Cómo usar APIs", format:"short", retention:0.42, ctr:0.06}),
       (:Video {id:"vid6", title:"Apps productividad", format:"short", retention:0.47, ctr:0.05}),
       (:Video {id:"vid7", title:"Embudo en 60s", format:"short", retention:0.51, ctr:0.08}),
       (:Video {id:"vid8", title:"Copy que convierte", format:"short", retention:0.48, ctr:0.07}),
       (:Video {id:"vid9", title:"Retención de clientes", format:"short", retention:0.46, ctr:0.06});
MATCH (t:Topic {name:"fitness"}),     (v:Video) WHERE v.id IN ["vid1","vid2","vid3"] MERGE (v)-[:TIENE_TEMA]->(t);
MATCH (t:Topic {name:"tecnologia"}), (v:Video) WHERE v.id IN ["vid4","vid5","vid6"] MERGE (v)-[:TIENE_TEMA]->(t);
MATCH (t:Topic {name:"marketing"}),  (v:Video) WHERE v.id IN ["vid7","vid8","vid9"] MERGE (v)-[:TIENE_TEMA]->(t);
