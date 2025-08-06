sudo apt install python3-dev python3-pip build-essential

sudo apt install i2c-tools python3-smbus


``pip install -r requirements.txt``


Build binary for python wrapper

```
cd bsec/rpi/bin/ && gcc -shared -fPIC -I./inc -o libbsec_wrapper.so bsec_py_wrapper.c config2/bsec_iaq.c libalgobsec.a -lm && cd -
```
