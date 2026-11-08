#include "graphTool/graphTool.h"
#include <cstdint>
#include <iostream>
#include <stdexcept>
std::uint32_t repro_seed=5012;
int main(int argc,char** argv){
    try{
        if(argc!=5) throw std::runtime_error("Usage: generate_synthetic OUTPUT NODES EDGES SEED");
        const auto nodes=std::stoull(argv[2]),edges=std::stoull(argv[3]),seed=std::stoull(argv[4]);
        if(nodes<3 || edges<3 || seed>UINT32_MAX) throw std::runtime_error("Invalid parameters");
        repro_seed=static_cast<std::uint32_t>(seed);
        generateHypergraph_nbr_PowerLaw(nodes,edges,argv[1]);
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}
}
