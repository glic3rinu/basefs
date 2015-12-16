/* Partialy based on https://code.google.com/p/pcapsctpspliter/issues/detail?id=6 */
// To compile: g++ timing.cpp -lpcap -lssl -lcrypto -lsketches -I<SKETCHES_DIR> -o timing -std=c++11
#include <pcap.h>
#include <stdlib.h>
#include <netinet/ip.h>
#include <arpa/inet.h>
#include <openssl/md5.h>
#include <time.h>           /* clock_t, clock, CLOCKS_PER_SEC */

#include "sketches.h"

//defines for the packet type code in an ETHERNET header
#define ETHER_TYPE_IP (0x0800)
#define ETHER_TYPE_IPv6 (0x86DD)

uint64_t high_md5 (unsigned char* hash){
    uint64_t result = hash[15] << 56 + hash[14] << 48 + hash[13] << 40 + 
                        hash[12] << 32 + hash[11] << 24 + hash[10] << 16 + 
                        hash[9]<<8 + hash[8];
    return result;
}

uint64_t low_md5 (unsigned char* hash){
    uint64_t result = hash[7] << 56 + hash[6] << 48 + hash[5] << 40 + 
                        hash[4] << 32 + hash[3] << 24 + hash[2] << 16 + 
                        hash[1]<<8 + hash[0];
    return result;
}

template<typename KeyType>
Sketch<KeyType>* get_sketch(char* sketch_type, unsigned buckets, 
                            unsigned rows, char* random_generator, 
                            char* hash_function){
    
    Sketch<KeyType>* sketch;
    
    if (strcmp(sketch_type, "FastCount") == 0) {
        sketch = new FastCount_Sketch<KeyType>(buckets, rows, random_generator);
    } else if (strcmp(sketch_type, "AGMS") == 0) {
        sketch = new AGMS_Sketch<KeyType>(buckets, rows, random_generator, 
            "mean");
    } else if (strcmp(sketch_type, "FAGMS") == 0) {
        sketch = new FAGMS_Sketch<KeyType>(buckets, rows, hash_function, 
            random_generator, "mean");
    } else {
        fprintf(stderr, "Invalid sketch type\n");
        return NULL;
    }
    return sketch;
}

template<typename KeyType>
int test_sketch(char* sketch_type, unsigned buckets, unsigned rows, 
                    char* random_generator, char* hash_function,
                    char* pcap_file){
    unsigned int pkt_counter=0;   // packet counter 
    clock_t t1, t2, t3;
    //temporary packet buffers 
    struct pcap_pkthdr header; // The header that pcap gives us 
    const u_char *packet; // The actual packet 
    // Create the sketch as the type passed as parameter
    Sketch<KeyType>* sketch = get_sketch<KeyType>(sketch_type, buckets, rows, 
        random_generator, hash_function);
    if (sketch == NULL) {
        return -1;
    }
    //----------------- 
    //open the pcap file 
    pcap_t *handle; 
    char errbuf[PCAP_ERRBUF_SIZE];
    handle = pcap_open_offline(pcap_file, errbuf);   //call pcap library function 

    if (handle == NULL) {
        fprintf(stderr,"Couldn't open pcap file %s: %s\n", pcap_file, errbuf);
        return -1;
    }

    //----------------- 
    //Process one packet at a time
    while (packet = pcap_next(handle,&header)) {
        t1 = clock();
        // header contains information about the packet (e.g. timestamp) 
        u_char *pkt_ptr = (u_char *)packet; //cast a pointer to the packet data 
        //parse the first (ethernet) header, grabbing the type field 
        int ether_type = ((int)(pkt_ptr[12]) << 8) | (int)pkt_ptr[13]; 
        int ether_offset = 0; 

        if (ether_type == ETHER_TYPE_IP or ether_type == ETHER_TYPE_IPv6) //most common 
            ether_offset = 14; 
        else {
            fprintf(stderr, "Unknown ethernet type, %04X, skipping...\n", ether_type); 
            continue;
        }
        // Only from IP header:
        pkt_ptr += ether_offset;  //skip past the Ethernet II header 
        int packet_length = header.len-ether_offset;

        // Compute MD5
        unsigned char * tmp_hash;
        tmp_hash = MD5(pkt_ptr, packet_length, NULL);
        // Strip to the size of the sketch:
        uint64_t low_hash = low_md5(tmp_hash);
        
        // Update sketch
        t2 = clock();

        sketch->update(low_hash,1);
        t3 = clock();

        printf("%s,%u,%u,%u,%s,%s,%f,%f,%f,%f\n",
                sketch_type,
                sizeof(KeyType),
                buckets,
                rows,
                random_generator,
                hash_function,
                ((float)t1)/CLOCKS_PER_SEC, 
                ((float)t2)/CLOCKS_PER_SEC, 
                ((float)t3)/CLOCKS_PER_SEC,
                ((float)t3-t1)/CLOCKS_PER_SEC);
        pkt_counter++; //increment number of packets seen 
        
        if (pkt_counter >= 1000)
            break;

    } //end internal loop for reading packets (all in one file) 

    pcap_close(handle);  //close the pcap file 
    return 0; //done
}
// TODO move to a function

int main(int argc, char **argv) 
{
    //check command line arguments 
    if (argc < 7) { 
        fprintf(stderr, "Usage: %s pcap_file sketch_type hash_length "
            "num_buckets num_rows random_generator [hash_function]\n", argv[0]); 
        exit(EXIT_FAILURE); 
    } 

    unsigned buckets = atoi(argv[4]);
    unsigned rows = atoi(argv[5]);
    unsigned hash_length = atoi(argv[3]);
    char* hash_function;
    if (argc == 7) hash_function = "cw2";
    else hash_function = argv[7];
    int result;
    
    switch(hash_length){
        case 8:
            result = test_sketch<uint8_t>(argv[2], buckets, rows, argv[6], 
                hash_function, argv[1]);
            break;
        case 16:
            result = test_sketch<uint16_t>(argv[2], buckets, rows, argv[6], 
                hash_function, argv[1]);
            break;
        case 32:
            result = test_sketch<uint32_t>(argv[2], buckets, rows, argv[6], 
                hash_function, argv[1]);
            break;
        case 64:
            result = test_sketch<uint64_t>(argv[2], buckets, rows, argv[6], 
                hash_function, argv[1]);
            break;
        case 128:
            result = test_sketch<uint128_t>(argv[2], buckets, rows, argv[6], 
                hash_function, argv[1]);
            break;
        default:
            fprintf(stderr, "Invalid hash length: %i\n", hash_length);
            break;
    }
    return result;
}
