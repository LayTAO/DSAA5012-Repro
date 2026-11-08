#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
int main(int argc,char** argv){
    try{
        if(argc!=2)throw std::runtime_error("Usage: audit_hypergraph INPUT");
        std::ifstream input(argv[1]);if(!input)throw std::runtime_error("Cannot open input");
        std::vector<std::uint64_t> seen;std::uint64_t vertices=0,edges=0,incidences=0,maxedge=0,maxid=0,minid=UINT64_MAX;
        std::string line;bool sorted=true;
        while(std::getline(input,line)){
            std::uint64_t value=0,size=0,previous=0;bool digits=false;
            auto finish=[&](){
                if(!digits)return;
                if(value==0 || value>2000000000ULL)throw std::runtime_error("Node ID outside supported 1..2 billion range");
                if(size && value<=previous)sorted=false;
                previous=value;const std::uint64_t word=value/64,mask=1ULL<<(value%64);
                if(word>=seen.size())seen.resize(word+1,0);
                if(!(seen[word]&mask)){seen[word]|=mask;++vertices;}
                ++size;maxid=std::max(maxid,value);minid=std::min(minid,value);value=0;digits=false;
            };
            for(char c:line){
                if(c>='0'&&c<='9'){value=value*10+(c-'0');digits=true;if(value>2000000000ULL)throw std::runtime_error("Node ID exceeds limit");}
                else if(c==','||c==' '||c=='\t'||c=='\r')finish();
                else throw std::runtime_error("Invalid input character");
            }
            finish();if(!size)continue;++edges;incidences+=size;maxedge=std::max(maxedge,size);
        }
        if(!vertices)throw std::runtime_error("Empty hypergraph");
        std::cout<<"{\"vertices\":"<<vertices<<",\"edges\":"<<edges<<",\"incidences\":"<<incidences
                 <<",\"max_edge_size\":"<<maxedge<<",\"max_vertex_id\":"<<maxid
                 <<",\"dense_vertex_ids\":"<<((minid==1&&vertices==maxid)?"true":"false")
                 <<",\"strictly_sorted_members\":"<<(sorted?"true":"false")<<"}\n";
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}
}
