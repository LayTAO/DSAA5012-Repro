#include "Hypergraph.h"
#include <iostream>
#include <iomanip>
int main(int argc,char**argv){try{
 if(argc!=2)return 2;Hypergraph g;g.loadFromFiles(argv[1]);
 std::uint64_t zero=0,one=0,two=0,slow=0,union_work=0,hash_work=0,scan_work=0;
 for(std::size_t v=1;v<g.getGraphNodeSize();v++){
  auto es=g.getEdges(v);auto deg=es.second-es.first;
  if(!deg){++zero;continue;}
  if(deg==1){++one;continue;}
  if(deg==2){++two;for(auto i=es.first;i<es.second;i++){auto nodes=g.getNodes(g.node_edge_simplices[i]);union_work+=nodes.second-nodes.first;}continue;}
  ++slow;for(auto i=es.first;i<es.second;i++){auto ns=g.getNodes(g.node_edge_simplices[i]);scan_work+=ns.second-ns.first;hash_work+=ns.second-ns.first-1;}
 }
 std::cout<<"INIT_WORK {\"degree0_vertices\":"<<zero<<",\"degree1_vertices\":"<<one<<",\"degree2_vertices\":"<<two<<",\"degree_ge3_vertices\":"<<slow<<",\"degree2_union_input_items\":"<<union_work<<",\"slow_path_node_visits\":"<<scan_work<<",\"slow_path_hash_insert_attempts\":"<<hash_work<<"}\n";
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 2;}}
