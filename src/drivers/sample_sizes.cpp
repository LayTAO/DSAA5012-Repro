#include "graphTool/graphTool.h"
#include <cstdint>
#include <iostream>
#include <stdexcept>
std::uint32_t repro_seed=5012;
int main(int argc,char** argv){
    try{
        if(argc!=3)throw std::runtime_error("Usage: sample_sizes INPUT SEED");
        const auto seed=std::stoull(argv[2]);if(seed>UINT32_MAX)throw std::runtime_error("Invalid seed");
        repro_seed=static_cast<std::uint32_t>(seed);vary_edges(argv[1]);
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}
}
