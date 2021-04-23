from getpass import getpass
cust_user = '1234'
cust_pass = 'pass'
priceCapu = 70
priceLatt = 70
priceCacao = 75
priceSoda = 50
sumCapu = 0
sumLatt = 0
sumCacao = 0
sumSoda = 0
inputUser = input('Username: ')
inputPass = getpass('Password: ')
if inputUser == cust_user and inputPass == cust_pass:
    print('---------- Welcome to Shiawase Cafe ---------')
    print('------------------ Menu ---------------------')
    print('1. Capuchino           70 THB')
    print('2. Latte               70 THB')
    print('3. Cacao               75 THB')
    print('4. Italian Soda        50 THB')
    select_Product = int(input('รับอะไรดีครับ? (ตัวเลขเมนูที่ต้องการ) : '))
    while select_Product != 0:
        if select_Product == 1:
            print('Capuchino', priceCapu)
            orderCapu = int(input('รับกี่แก้วครับ? : '))
            sumCapu = orderCapu * priceCapu
            select_Product = int(input('รับอะไรเพิ่มมั้ยครับ? (ตัวเลขเมนูที่ต้องการ หากไม่รับกรุณากด 0) : '))
        elif select_Product == 2:
            print('Latte', priceLatt)
            orderLatt = int(input('รับกี่แก้วครับ? : '))
            sumLatt = orderLatt * priceLatt
            select_Product = int(input('รับอะไรเพิ่มมั้ยครับ? (ตัวเลขเมนูที่ต้องการ หากไม่รับกรุณากด 0) : '))
        elif select_Product == 3:
            print('Cacao', priceCacao)
            orderCacao = int(input('รับกี่แก้วครับ? : '))
            sumCacao = orderCacao * priceCacao
            select_Product = int(input('รับอะไรเพิ่มมั้ยครับ? (ตัวเลขเมนูที่ต้องการ หากไม่รับกรุณากด 0) : '))
        elif select_Product == 4:
            print('Italian Soda', priceSoda)
            orderSoda = int(input('รับกี่แก้วครับ? : '))
            sumSoda = orderSoda * priceSoda
            select_Product = int(input('รับอะไรเพิ่มมั้ยครับ? (ตัวเลขเมนูที่ต้องการ หากไม่รับกรุณากด 0) : '))
    else:
        sumOrder = sumCapu + sumLatt + sumCacao + sumSoda
        print('ยอดรวมทั้งหมด', sumOrder,'THB')
        print('----------Thank you----------')
else:
    print('Invalid Username or Password!!!')
