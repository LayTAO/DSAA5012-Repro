#pragma once
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <time.h>
#include <vector>
#include <x86intrin.h>
namespace supplement {
// MFENCE orders preceding stores; RDTSCP orders preceding execution/loads;
// LFENCE prevents subsequent instructions crossing the timestamp. Compiler
// barriers surround each stamp. Affinity and AUX consistency are checked.
struct Stamp {std::uint64_t t; unsigned aux;};
inline Stamp stamp(){
 asm volatile("" ::: "memory"); _mm_mfence();unsigned aux;
 const auto t=__rdtscp(&aux);_mm_lfence();asm volatile("" ::: "memory");return {t,aux};
}
inline double wall(){timespec t{};if(clock_gettime(CLOCK_MONOTONIC_RAW,&t))throw std::runtime_error("clock_gettime");return t.tv_sec+t.tv_nsec*1e-9;}
inline void pause_ms(long ms){timespec t{ms/1000,(ms%1000)*1000000};while(nanosleep(&t,&t)){} }
struct Region {std::uint64_t calls=0,samples=0,cycles=0;};
struct Start {bool selected;Stamp value;};
struct Timer {
 double hz=0,pair_median=0,pair_min=0,pair_p95=0,freq_spread=0;
 std::uint64_t seed=5012,migrations=0;unsigned stride=1;Region regions[2];
 Timer(){
  if(const char* v=std::getenv("REPRO_TIMER_STRIDE"))stride=std::stoul(v);
  if(stride!=1&&stride!=32)throw std::runtime_error("Timer stride must be 1 or 32");
  if(const char* v=std::getenv("REPRO_TIMER_SEED"))seed=std::stoull(v);
  std::vector<double>freq;for(int i=0;i<5;i++){double a=wall();auto x=stamp();pause_ms(100);auto y=stamp();double b=wall();if(x.aux!=y.aux)throw std::runtime_error("Calibration migrated");freq.push_back(double(y.t-x.t)/(b-a));}
  std::sort(freq.begin(),freq.end());hz=freq[2];freq_spread=(freq.back()-freq.front())/hz;
  if(freq_spread>.005)throw std::runtime_error("Unstable TSC calibration (>0.5%)");
  std::vector<std::uint64_t>overhead;overhead.reserve(20001);
  for(int i=0;i<20001;i++){auto a=stamp();auto b=stamp();if(a.aux!=b.aux)throw std::runtime_error("Timer migrated");overhead.push_back(b.t-a.t);}
  std::sort(overhead.begin(),overhead.end());pair_min=overhead.front();pair_median=overhead[10000];pair_p95=overhead[19000];
 }
 static std::uint64_t mix(std::uint64_t x){x+=0x9e3779b97f4a7c15ULL;x=(x^(x>>30))*0xbf58476d1ce4e5b9ULL;x=(x^(x>>27))*0x94d049bb133111ebULL;return x^(x>>31);}
 Start begin(unsigned r){auto n=++regions[r].calls;bool yes=stride==1||(mix(n^seed^(std::uint64_t(r+1)<<48))&(stride-1))==0;return {yes,yes?stamp():Stamp{0,0}};}
 void end(unsigned r,Start a){if(!a.selected)return;auto b=stamp();if(a.value.aux!=b.aux){++migrations;return;}++regions[r].samples;regions[r].cycles+=b.t-a.value.t;}
 double seconds(unsigned r,bool adjust=false)const{double cyc=regions[r].cycles-(adjust?pair_median*regions[r].samples:0);return cyc*stride/hz;}
 void print()const{
  std::cout<<std::setprecision(17)<<"SUPPLEMENT_TIMER {\"stride\":"<<stride<<",\"seed\":"<<seed<<",\"tsc_hz\":"<<hz<<",\"frequency_relative_spread\":"<<freq_spread<<",\"pair_overhead_cycles_median\":"<<pair_median<<",\"pair_overhead_cycles_min\":"<<pair_min<<",\"pair_overhead_cycles_p95\":"<<pair_p95<<",\"migrations\":"<<migrations;
  for(unsigned r=0;r<2;r++){const char* k=r==0?"C":"D";std::cout<<",\""<<k<<"\":{\"calls\":"<<regions[r].calls<<",\"samples\":"<<regions[r].samples<<",\"sample_cycles\":"<<regions[r].cycles<<",\"raw_estimate_s\":"<<seconds(r)<<",\"empty_pair_adjusted_estimate_s\":"<<seconds(r,true)<<"}";}
  std::cout<<"}\n";
 }
};
inline Timer& timer(){static Timer t;return t;}
}
