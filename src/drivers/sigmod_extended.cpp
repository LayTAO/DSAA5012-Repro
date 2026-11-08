#include "Hypergraph.h"
#include "Algorithm/NbrCD.h"
#include "Algorithm_withInfo/NbrCD.h"
#include "metrics.h"
#include <fstream>
#include <stdexcept>
#include <string>

int main(int argc, char** argv) {
    try {
        if (argc != 6) throw std::runtime_error("Usage: sigmod_extended INPUT stats|parallel ALGORITHM_OR_THREADS THRESHOLD CORE_CSV_OR_DASH");
        const std::string mode(argv[2]);
        const int argument=std::stoi(argv[3]), threshold=std::stoi(argv[4]);
        if (mode!="stats" && mode!="parallel") throw std::runtime_error("Unknown mode");
        if (mode=="stats" && (argument<0 || argument>6)) throw std::runtime_error("Stats algorithm must be 0..6");
        if (mode=="parallel" && (argument<1 || argument>64 || threshold<1)) throw std::runtime_error("Invalid threads/threshold");
        using Fn=void (*)(Hypergraph&);
        const Fn algorithms[]={withInfo::nbrCoreDecomposition,withInfo::nbrCoreDecomposition_onlyChanged,
            withInfo::nbrCoreDecomposition_onlyLowerBound,withInfo::nbrCoreDecomposition_no_filter,
            withInfo::baseNbrCoreDecomposition_withNbrs,withInfo::fullNbrCoreDecomposition,
            withInfo::nbrCoreDecomposition_withNbrs};
        const auto start=ReproClock::now();
        Hypergraph graph;graph.loadFromFiles(argv[1]);
        if(mode=="parallel" && (graph.getAvgDegree()==0 || graph.getAvgEdgeSize()==0))
            throw std::runtime_error("UPSTREAM_UNSUPPORTED: parallel scheduler divides by a rounded average of zero");
        std::size_t vertices=0;
        for(std::size_t v=1;v<graph.getGraphNodeSize();++v){auto e=graph.getEdges(v);if(e.second>e.first)++vertices;}
        const auto loaded=ReproClock::now();
        if(mode=="stats") algorithms[argument](graph);
        else ParNbrCoreDecomposition(graph,argument,threshold);
        const auto computed=ReproClock::now();
        metrics(seconds(start,loaded),0,seconds(loaded,computed),vertices);
        if(std::string(argv[5])!="-"){
            std::ofstream out(argv[5]);out.exceptions(std::ios::failbit|std::ios::badbit);out<<"vertex,core\n";
            for(std::size_t v=1;v<graph.getGraphNodeSize();++v){auto e=graph.getEdges(v);if(e.second>e.first)out<<v<<','<<graph.nodes_core.at(v)<<'\n';}
        }
    } catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 2;}
}
