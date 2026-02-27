"""
Скрипт для обновления текста вопросов в базе данных
"""

from app import app, db, SelectionQuestion

def update_question_text():
    with app.app_context():
        print("Обновление текста вопросов...")
        
        try:
            # Находим первый вопрос (с order=1)
            question = SelectionQuestion.query.filter_by(order=1).first()
            
            if question:
                old_text = question.question_text
                new_text = 'Представим такую ситуацию, я - ищу работу чаттером , повесил вакансию на доске , ваша задача - переманить меня на работу оператором : зп от 65к р , график 5/2 4/3 (смысл заклбчается в модерации стримов модели ноу-нюд формата , то есть без 18+) смены от 6 часов'
                
                print(f"Старый текст вопроса: {old_text}")
                print(f"Новый текст вопроса: {new_text}")
                
                question.question_text = new_text
                db.session.commit()
                
                print("✓ Текст вопроса успешно обновлен!")
            else:
                print("⚠ Вопрос с order=1 не найден")
                
        except Exception as e:
            print(f"✗ Ошибка при обновлении: {str(e)}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    update_question_text()
